# ESMC Sparse Autoencoders (SAEs)

SAEs decompose ESMC's hidden representations into a **sparse set of
interpretable features**. For ESMC-6B the released codebook has **16 384
features**, each with an agent-generated natural-language description (the
"world model" the paper claims has been "materialized"). The Atlas page on
biohub.ai uses these.

Two flavors of access:

- **Local** — load `Biohub/ESMC-6B-sae-…` as a plain HF AutoModel and
  inject into ESMC.
- **Cloud (Biohub Platform)** — pass a `SAEConfig` in your `LogitsConfig`;
  the platform returns sparse features.

## What an SAE codebook looks like

The released codebooks are parametrised:

- **k = 64** — top-K activations per token (sparsity)
- **codebook size = 16 384** — number of features
- **layer** — which ESMC layer it was trained against

Concrete checkpoint names (HF):

| HF repo | ESMC layers covered | Notes |
|---------|---------------------|-------|
| `Biohub/ESMC-6B-sae-layer60-k64-codebook16384` | 60 | The codebook used in the paper / Atlas (most analyzed) |
| `Biohub/ESMC-6B-sae-k64-codebook16384` | 30 + 60 | Bundle covering both layers |
| `Biohub/ESMC-300M-sae-…` | varies | 300M variants — **no normalization** |

The 300M family was trained without per-feature normalization stats — see
the warning below.

## Local — load and inject

```python
import torch
from transformers import AutoModel, AutoTokenizer

# 1) ESMC backbone
model = AutoModel.from_pretrained("Biohub/ESMC-6B", device_map="auto").eval()
tokenizer = AutoTokenizer.from_pretrained("Biohub/ESMC-6B")

# 2) SAE codebook — only download the layers you'll use
sae = AutoModel.from_pretrained(
    "Biohub/ESMC-6B-sae-k64-codebook16384",
    allow_patterns=["config.json", "layer_30.safetensors", "layer_60.safetensors"],
    device=model.device,
)
sae.initialize_layers([30, 60])
model.add_sae_models([sae.layers["30"], sae.layers["60"]])

# 3) Forward — outputs gain a "sae_outputs" key
sequence = "MGSNKSKPKDASQRRRSLEPAENVHGAGGG..."
inputs = tokenizer(sequence, return_tensors="pt", padding=True)
inputs = {k: v.to(model.device) for k, v in inputs.items()}
with torch.inference_mode():
    output = model(**inputs)

sae60 = output["sae_outputs"]["layer60"]    # torch.sparse_coo_tensor, (1, L+2, 16384)
print(sae60.shape, sae60.indices().shape)
```

`output["sae_outputs"]` is a `dict[str, torch.sparse.Tensor]` keyed by
layer name (`"layer30"`, `"layer60"`, …). Each tensor has shape
`(B, L+2, codebook_size)`, sparse COO format — densify with
`.to_dense()` if you need to (heavy: 16 K dims).

`allow_patterns` is a `huggingface_hub.snapshot_download` filter — without
it you download every layer's safetensors, which adds up.

## Cloud — `SAEConfig`

```python
import os
from esm.sdk import esmc_client
from esm.sdk.api import ESMProtein, LogitsConfig, SAEConfig

client = esmc_client(model="esmc-6b-2024-12", token=os.environ["ESM_API_KEY"])

sae_cfg = SAEConfig(
    models=["ESMC-6B-sae-layer60-k64-codebook16384"],
    normalize_features=True,       # MUST be False for any 300M SAE
)

protein = ESMProtein(sequence="MGSNKSKPKDASQRR...")
pt = client.encode(protein)
out = client.logits(pt, LogitsConfig(sae_config=sae_cfg), return_bytes=False)

sae_tensor = out.sae_outputs[sae_cfg.models[0]]    # torch sparse COO
```

`SAEConfig` schema:

```python
@define
class SAEConfig:
    models: list[str] = []
    normalize_features: bool = True
    model: str | None = None     # deprecated alias — use `models`

    # __attrs_post_init__: raises ValueError if both `model` and `models` set;
    # raises if normalize_features=True and any model name contains "300m"
```

So:

- **Use `models=[...]`**, not `model=...` (the latter is deprecated and
  warns).
- **Set `normalize_features=False`** if any model name is a 300M SAE.
  Otherwise the post-init raises a `ValueError` listing the bad name(s).
- You can pass multiple SAE model names in `models=[...]` — the result is
  a dict keyed by each.

## Densifying + pooling features

The cookbook snippet (`cookbook/snippets/sae.py` + `sparse_utils.py`) shows
the typical post-processing:

```python
from cookbook.snippets.sparse_utils import max_pool, remove_indexes

# sae_tensor is sparse, shape (L+2, 16384)
features = remove_indexes(sae_tensor, {0, -1})      # drop BOS/EOS
pooled   = max_pool(features, axis=0)               # (16384,) max over tokens
```

`max_pool` / `remove_indexes` operate on COO tensors directly so you never
densify. The pooled vector is what you use for per-protein retrieval /
clustering / similarity.

## Batched extraction (parallel over sequences)

From `cookbook/snippets/sae.py`:

```python
import os
from esm.sdk import esmc_client, batch_executor
from esm.sdk.api import ESMProtein, ESMProteinError, LogitsConfig, SAEConfig
from cookbook.snippets.sparse_utils import max_pool, remove_indexes

client = esmc_client(model="esmc-6b-2024-12", token=os.environ["ESM_API_KEY"])
sae_cfg = SAEConfig(models=["ESMC-6B-sae-layer60-k64-codebook16384"])

def _features(client, sequence: str, pool: bool = True):
    pt = client.encode(ESMProtein(sequence=sequence))
    if isinstance(pt, ESMProteinError):
        raise ValueError(pt.error_msg)
    out = client.logits(pt, LogitsConfig(sae_config=sae_cfg), return_bytes=False)
    if isinstance(out, ESMProteinError):
        raise ValueError(out.error_msg)
    if out.sae_outputs is None:
        raise ValueError(f"missing sae_outputs: {out}")
    t = out.sae_outputs[sae_cfg.models[0]]
    if pool:
        return max_pool(remove_indexes(t, {0, -1}), axis=0)
    return t

with batch_executor() as ex:
    feats = ex.execute_batch(
        user_func=_features, client=client,
        sequence=["MKTL...","MGSN...","..."], pool=True,
    )
```

`batch_executor` retries failed requests up to `max_attempts=10` by default
and shows a progress bar.

## Interpreting features

Each SAE feature has a natural-language description generated by an
agentic pipeline that maps activations back to known biology (InterPro,
EC, GO …). The descriptions ship alongside the codebook on HF — typical
loading:

```python
from huggingface_hub import hf_hub_download
import json
desc_path = hf_hub_download(
    "Biohub/ESMC-6B-sae-layer60-k64-codebook16384",
    "feature_descriptions.json",       # or similar — check the model card
)
descriptions = json.load(open(desc_path))   # {feature_idx: "natural language"}
```

Top-N features per protein:

```python
import torch
indices = pooled.indices()           # (1, nnz)
values  = pooled.values()            # (nnz,)
topk = torch.topk(values, k=10)
for v, idx in zip(topk.values, topk.indices):
    feat = int(indices[0, idx])
    print(f"{feat:5d}  {v.item():6.3f}  {descriptions.get(str(feat))}")
```

## Tutorials

`cookbook/tutorials/esmc_sae_feature_interpretation.ipynb` is the canonical
walkthrough:

- Extract features for a sequence.
- Rank by peak activation and prevalence.
- Map activations onto 3D structure (using a paired ESMFold2/PDB
  structure) to see *which residues* trigger a feature.
- Compare features across a set of homologs.

## Gotchas

1. **300M SAE → `normalize_features=False`.** Hard-coded in the post-init
   check; you'll get a `ValueError` listing the offending model name.
2. **`SAEConfig(model=...)` is deprecated.** Triggers a
   `DeprecationWarning`; switch to `models=[...]`.
3. **Sparse outputs.** Don't `.to_dense()` blindly — a single sequence's
   features can be (L, 16 384). Use `max_pool` / `remove_indexes` from
   `cookbook/snippets/sparse_utils.py`.
4. **BOS/EOS are present** in the SAE tensor (positions 0 and L+1). The
   `remove_indexes(t, {0, -1})` helper strips them.
5. **`allow_patterns` matters at download time.** Without it, you fetch
   every layer's safetensors — that's many GB. Always restrict to the
   layers you actually use.
