# ESMC — protein language model

ESMC (ESM Cambrian) is an **encoder-only transformer** trained on billions of
protein sequences. Three sizes: 300M (open), 600M (open), 6B (gated). All have
the same API surface; bigger = better representations + slower.

## Two API styles

ESMC can be used through:

1. **Native HF Transformers** — `AutoModelForMaskedLM.from_pretrained("Biohub/ESMC-6B")`.
   What the upstream README shows. Simple, but ties you to HF idioms.
2. **The `esm.sdk` API** — `ESMC.from_pretrained("esmc_600m")` + the
   `ESMProtein`/`ESMProteinTensor` dataclasses. Recommended because the
   **same code runs locally and against the Biohub Platform** (you just swap
   the client object for an `ESMCForgeInferenceClient`).

Both end up calling the same model code in `esm.models.esmc`. Pick the SDK
style if you might ever scale to the cloud API; pick HF style if you want
the model object directly (e.g. for fine-tuning).

## HF style (the README path)

```python
import torch
from transformers import AutoModelForMaskedLM, AutoTokenizer
from huggingface_hub import login
login()                                             # only needed for gated weights

tokenizer = AutoTokenizer.from_pretrained("Biohub/ESMC-6B")
model = AutoModelForMaskedLM.from_pretrained("Biohub/ESMC-6B", device_map="auto").eval()

inputs = tokenizer(["MSKGEELFT..."], return_tensors="pt", padding=True)
inputs = {k: v.to(model.device) for k, v in inputs.items()}
with torch.inference_mode():
    out = model(**inputs, output_hidden_states=True)
out.logits.shape         # (B, L+2, V)
out.hidden_states        # tuple of (n_layers + 1) tensors of (B, L+2, d)
```

`output_hidden_states=True` returns **every** layer; without it you get only
the final.

> The Biohub Platform's REST API has a server-side optimization: for
> `esmc-6b` it can return *only one* hidden layer per request to save
> bandwidth. `esm.utils.constants.models.forge_only_return_single_layer_hidden_states("esmc-6b")`
> returns `True` for this case — set `ith_hidden_layer=N` in `LogitsConfig`
> to pick which.

## SDK style — `ESMProtein` + `LogitsConfig`

```python
from esm.models.esmc import ESMC
from esm.sdk.api import ESMProtein, LogitsConfig

model = ESMC.from_pretrained("esmc_600m")                 # cuda+bf16 if avail
protein = ESMProtein(sequence="MKTLLILAVL...")
protein_tensor = model.encode(protein)                    # ESMProteinTensor

out = model.logits(
    protein_tensor,
    LogitsConfig(sequence=True,
                 return_embeddings=True,
                 return_hidden_states=True,
                 ith_hidden_layer=-1),                    # -1 = last; default
)
out.logits.sequence       # (1, L+2, V)
out.embeddings            # (1, L+2, d) — sequence-aligned per-token embedding
out.hidden_states         # (1, L+2, d) — single layer (because ith_hidden_layer)
```

Drop in a remote client and the same call works against the platform:

```python
from esm.sdk import esmc_client
client = esmc_client(model="esmc-600m-2024-12", token=os.environ["ESM_API_KEY"])
out = client.logits(client.encode(protein),
                    LogitsConfig(sequence=True, return_embeddings=True))
```

### `LogitsConfig` (the one you care about for ESMC)

| Field | What it does |
|-------|-------------|
| `sequence: bool` | Return per-token sequence logits |
| `return_embeddings: bool` | Return per-token final-layer embeddings (post-LN) |
| `return_hidden_states: bool` | Return one layer's hidden states |
| `return_mean_embedding: bool` | Return the mean over tokens (pooled vector) |
| `return_mean_hidden_states: bool` | Mean pooled hidden states |
| `ith_hidden_layer: int = -1` | Which layer for `return_hidden_states` (negative indices supported) |
| `sae_config: SAEConfig` | Attach SAE feature extraction; see `references/sae.md` |
| `structure/secondary_structure/sasa/function/residue_annotations` | Other tracks — **not supported for ESMC on the Biohub Platform** (response sizes are too big). They work locally with ESM3 only. |

### `LogitsOutput`

```python
@define
class LogitsOutput:
    logits: ForwardTrackData | None         # .sequence, .structure, …
    embeddings: torch.Tensor | None         # (B, L+2, d)
    mean_embedding: torch.Tensor | None     # (B, d)
    hidden_states: torch.Tensor | None      # (B, L+2, d)  — single layer
    mean_hidden_state: torch.Tensor | None  # (B, d)
    residue_annotation_logits: torch.Tensor | None    # multi-hot Bernoulli
    sae_outputs: dict[str, torch.Tensor] | None       # keyed by SAE model name
```

`L+2` because BOS / EOS tokens are added by the tokenizer.

## Raw forward (skip `encode`/`decode`)

Useful for batching or when you don't need the `ESMProtein` wrapper:

```python
model = ESMC.from_pretrained("esmc_300m")
seqs = ["AAAAA", "MKTLL..."]
input_ids = model._tokenize(seqs)
out = model(input_ids)
out.sequence_logits, out.embeddings, out.hidden_states
```

This is what the `cookbook/snippets/esmc.py::raw_forward` example does.

## Recipe — zero-shot mutation scoring (pseudo-perplexity)

The classic protein-LM use case: for each position, mask it, get the LM's
log-prob of the true amino acid, average. From `cookbook/snippets/esmc.py`:

```python
def compute_pseudoperplexity(client, sequence: str) -> float:
    import math, torch
    from esm.sdk.api import ESMProtein, LogitsConfig
    from esm.sdk import batch_executor
    from esm.tokenization import get_esmc_model_tokenizers

    L = len(sequence)
    masked = [sequence[:i] + "_" + sequence[i+1:] for i in range(L)]

    def _logits(client, sequence):
        pt = client.encode(ESMProtein(sequence=sequence))
        return client.logits(pt, LogitsConfig(sequence=True))

    with batch_executor() as ex:
        outs = ex.execute_batch(_logits, client=client, sequence=masked)

    vocab = get_esmc_model_tokenizers().get_vocab()
    lp = []
    for i, o in enumerate(outs):
        logits = o.logits.sequence              # (L+2, V)
        ls = torch.log_softmax(logits[i + 1], dim=-1)  # +1 = skip BOS
        lp.append(ls[vocab[sequence[i]]].item())

    return math.exp(-sum(lp) / L)
```

For local use, swap `client` for an `ESMC` model and `batch_executor` for a
plain loop.

## Recipe — per-position entropy / "constrained vs tolerant" sites

```python
import torch
out = model.logits(model.encode(ESMProtein(sequence=seq)),
                   LogitsConfig(sequence=True))
logits = out.logits.sequence[0, 1:-1]            # drop BOS/EOS  (L, V)
probs = torch.softmax(logits, dim=-1)
entropy = -(probs * probs.log()).sum(dim=-1)     # (L,)
```

Low entropy → ESMC is confident; the position is evolutionarily
constrained. High entropy → mutation-tolerant. This is what the
`esmc_mutation_scoring.ipynb` tutorial expands on.

## Recipe — layer sweep (pick the best layer for a downstream probe)

```python
hiddens = []
for layer in range(-model.transformer.n_layers, 0):    # -L … -1
    out = model.logits(protein_tensor,
                       LogitsConfig(return_hidden_states=True,
                                    ith_hidden_layer=layer))
    hiddens.append(out.hidden_states.mean(dim=1))      # mean-pool over tokens
```

Then train a linear probe on each `hiddens[k]`. The
`esmc_layer_sweep.ipynb` tutorial does this for an enzyme-classification
task; for many downstream tasks an intermediate layer (≈ 60-70% depth)
outperforms the final layer.

## Fine-tuning (PEFT)

`cookbook/tutorials/esmc_finetune.ipynb` walks through:

1. Wrap `ESMC` in a model with a classification / regression head.
2. Use `peft.LoraConfig` over the attention layers to keep the trainable
   parameter count low.
3. `Trainer` (from HF transformers) for the loop — the EvolutionaryScale
   fork plays nicely with `accelerate`, which is pre-installed in the SIF.

This is the only ESM workflow that **does not work via the Biohub Platform
API** — you need local weights. Use ESMC-300M or 600M unless you have
multi-GPU.

## Memory & throughput

Rough numbers on a single A100 80 GB (bf16, dense attention):

| Model | Forward, seq=512 | Forward, seq=2048 |
|-------|-------------------|--------------------|
| ESMC-300M | ~15 ms | ~50 ms |
| ESMC-600M | ~25 ms | ~90 ms |
| ESMC-6B | ~200 ms | ~750 ms |

With `flash_attn` available the 2048-token timings drop ~2-3×. For very
long sequences, plain dense attention is the bottleneck.

If you OOM on 6B + long sequences: lower batch to 1, use `device_map="auto"`
to spill across GPUs, or downcast to fp16 explicitly (the SDK uses bf16 by
default).
