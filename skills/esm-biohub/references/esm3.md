# ESM3 — generative protein model

ESM3 is the generative model that reasons jointly over **sequence**,
**structure** (3D backbone + residue tokens), **secondary structure**,
**SASA**, and **function** annotations. The same model can fold a sequence,
inverse-fold a backbone, predict function, scaffold a motif, or chain those
operations together. Released originally in `Science` 2025; an
`_assets/ESM3_README.md` in the repo has the long-form intro.

## What you can run locally

Only **`esm3-sm-open-v1`** (the open small model, ~1.4B params) is in the
local `LOCAL_MODEL_REGISTRY`. The medium / large checkpoints are
**Biohub Platform only** — get a key, use `client(...)`.

```python
from esm.models.esm3 import ESM3
from esm.sdk.api import ESMProtein, GenerationConfig

m = ESM3.from_pretrained("esm3_sm_open_v1")             # or "esm3-open"
# Aliases also accepted: esm3-sm-open-v1, esm3-open-2024-03, esm3-open
```

## `ESMProtein` — the universal container

`ESMProtein` has all five tracks + metrics:

```python
@define
class ESMProtein:
    sequence: str | None
    secondary_structure: str | None       # 1-letter SSE per residue: H/E/C
    sasa: list[float | None] | None
    function_annotations: list[FunctionAnnotation] | None
    coordinates: torch.Tensor | None      # (L, 37, 3) atom37
    plddt: torch.Tensor | None
    ptm: torch.Tensor | None
    pae: torch.Tensor | None
    crmsd: torch.Tensor | None
    globularity: torch.Tensor | None
    interface_annotations: list[str] | None
    interface_ptm: torch.Tensor | None
    pair_chains_iptm: torch.Tensor | None
    output_embedding_sequence: torch.Tensor | None
    output_embedding_pair_pooled: torch.Tensor | None
    residue_index: torch.Tensor | None
    entity_id: torch.Tensor | None
    potential_sequence_of_concern: bool = False
```

I/O:

```python
ESMProtein.from_pdb("x.pdb", chain_id="A")             # one chain
ESMProtein.from_pdb("x.pdb", chain_id="all")           # all chains (→ ProteinComplex)
ESMProtein.from_pdb("x.pdb", chain_id="detect")        # first detected
ESMProtein.from_protein_chain(chain)                   # from a biotite-backed ProteinChain
protein.to_pdb("out.pdb")
protein.to_pdb_string()
```

`from_pdb` reads coordinates AND sequence; `is_predicted=True` makes
B-factors load into `plddt`.

`ProteinChain.from_rcsb("1utn")` (in `esm.utils.structure.protein_chain`)
will fetch from RCSB if you have network — handy in examples.

## `GenerationConfig` — how to ask ESM3 for something

```python
@define
class GenerationConfig:
    track: str = ""                       # which track to generate
    invalid_ids: Sequence[int] = []       # token ids to disallow
    schedule: str = "cosine"              # or "linear"
    strategy: str = "random"              # or "entropy"
    num_steps: int = 20                   # ≤ sequence length
    temperature: float = 1.0
    temperature_annealing: bool = True
    top_p: float = 1.0
    condition_on_coordinates_only: bool = True   # for structure-only inputs
    only_compute_backbone_rmsd: bool = False
```

`track` is one of: `"sequence"`, `"structure"`, `"secondary_structure"`,
`"sasa"`, `"function"`.

Two presets:

```python
GenerationConfig(...).use_entropy_based_unmasking_strategy()
# → schedule="cosine", strategy="entropy", temperature_annealing=False
GenerationConfig(...).use_generative_unmasking_strategy()
# → schedule="cosine", strategy="random", temperature_annealing=True
```

## Common patterns (from `cookbook/snippets/esm3.py`)

### Fold a sequence

```python
protein = get_sample_protein()                    # sequence + coords from PDB
protein.coordinates = None                        # ← request structure
folded = client.generate(
    protein,
    GenerationConfig(track="structure", schedule="cosine",
                     num_steps=len(protein.sequence) // 16),
)
folded.to_pdb("folded.pdb")
```

### Inverse fold

```python
protein.sequence = None                           # ← request sequence
invf = client.generate(
    protein,
    GenerationConfig(track="sequence", schedule="cosine", num_steps=20),
)
invf.to_pdb("invfolded.pdb")     # writes sequence + coords
```

### Function prediction

```python
protein.function_annotations = None
out = client.generate(
    protein,
    GenerationConfig(track="function", schedule="cosine", num_steps=20),
)
out.function_annotations          # list[FunctionAnnotation]
```

### Partial-sequence completion ("fill in the blanks")

```python
prompt = ("_____________DQATSLRILNNGHAFNVEFDDSQDKAVLK"
          "GGPLDGTYRLIQFHFHWGSL_____________")
protein = ESMProtein(sequence=prompt)             # "_" = mask
out = client.generate(
    protein,
    GenerationConfig(track="sequence", num_steps=8, temperature=0.7),
)
out.sequence       # filled in
```

### Chain-of-thought across tracks

```python
prot = get_sample_protein()
prot.sequence = "_" * len(prot.sequence)
prot.coordinates = None
prot.sasa = None
pt = client.encode(prot)
for track in ("secondary_structure", "structure", "sequence"):
    pt = client.generate(pt, GenerationConfig(track=track, num_steps=10))
final = client.decode(pt)
final.to_pdb("cot.pdb")
```

`pt` stays as `ESMProteinTensor` between steps; you only decode at the end.

### Batch generation

```python
prompts = [ESMProtein(sequence="_" * (10 + 2*i)) for i in range(5)]
configs = [GenerationConfig(track="sequence", num_steps=i+1) for i in range(5)]
out = client.batch_generate(prompts, configs)
for i, p in enumerate(out):
    if isinstance(p, ESMProteinError):
        # one bad prompt won't kill the batch; check each result
        print(f"prompt {i} failed: {p.error_code} {p.error_msg}")
    else:
        p.to_pdb(f"batch_{i}.pdb")
```

`batch_generate` returns `Sequence[ESMProtein | ESMProteinError]`. Always
type-check.

## `forward_and_sample` — fine-grained sampling

For power users who want exact control over which tracks are sampled and
with which temperature / topk:

```python
from esm.sdk.api import SamplingConfig, SamplingTrackConfig
out = client.forward_and_sample(
    protein_tensor,
    SamplingConfig(structure=SamplingTrackConfig(topk_logprobs=2)),
)
out.protein_tensor          # ESMProteinTensor with the sampled tracks filled
out.entropy                 # ForwardTrackData of entropy per token per track
out.prob, out.logprob       # sampled-token probabilities
out.top_prob, out.topk_logprob, out.topk_tokens    # alternative-token info
```

## `ESMProteinTensor` — when you don't want raw representations

The token-space dataclass. Returned by `client.encode(ESMProtein)`; consumed
by `client.logits` / `client.forward_and_sample` / `client.generate` /
`client.decode`. Has the same tracks as `ESMProtein` but as integer token
tensors plus optional `coordinates`. `.to(device_or_dtype)` works.

## Raw forward (skip `client`, use the model directly)

`cookbook/local/raw_forwards.py` shows the low-level path used for research
code:

```python
from esm.pretrained import (
    ESM3_sm_open_v0, ESM3_structure_encoder_v0,
    ESM3_structure_decoder_v0, ESM3_function_decoder_v0,
)
from esm.tokenization import get_esm3_model_tokenizers
from esm.utils.structure.protein_chain import ProteinChain

tokenizers = get_esm3_model_tokenizers()
encoder    = ESM3_structure_encoder_v0("cuda")
model      = ESM3_sm_open_v0("cuda")

chain = ProteinChain.from_rcsb("1utn", "A")
coords, plddt, residue_index = chain.to_structure_encoder_inputs()
_, structure_tokens = encoder.encode(coords.cuda(), residue_index=residue_index.cuda())

# Add BOS/EOS padding, then forward
import torch.nn.functional as F
coords = F.pad(coords, (0,0, 0,0, 1,1), value=torch.inf)
structure_tokens = F.pad(structure_tokens, (1,1), value=0)
structure_tokens[:, 0] = 4098         # BOS
structure_tokens[:, -1] = 4097        # EOS

out = model.forward(structure_coords=coords, per_res_plddt=plddt,
                    structure_tokens=structure_tokens)
sequence = tokenizers.sequence.decode(out.sequence_logits.argmax(dim=-1)[0])
```

Output decoders (`ESM3_structure_decoder_v0`, `ESM3_function_decoder_v0`)
are loaded separately to save VRAM.

## ProteinComplex (multi-chain)

```python
from esm.utils.structure.protein_complex import ProteinComplex
pc = ProteinComplex.from_pdb("complex.pdb")
ep = ESMProtein.from_protein_complex(pc)
# Sequence has "|" between chains:  "MKT…|ACD…"
```

`SINGLE_LETTER_CHAIN_IDS` (also in `protein_complex`) is the canonical
chain-id list (`A`, `B`, …, `Z`, `0`, `1`, …) used when reconstructing.

## Things ESM3 does that ESMFold2 doesn't

- **Sequence generation conditioned on structure/function/SASA** —
  inverse folding, motif scaffolding, GFP-style de novo design.
- **Secondary-structure editing** (`track="secondary_structure"`).
- **InterPro function decoding** — assign function keywords to a
  predicted protein.

## Things ESMFold2 does that ESM3 doesn't

- **All-atom complexes** with nucleic acids and ligands.
- **AF3-class accuracy** on Foldbench.
- **MSA / template conditioning**.

Use ESMFold2 for structure prediction tasks; use ESM3 for generative /
multi-track work.

## GFP design walkthrough

`cookbook/tutorials/gfp_design.ipynb` walks through the exact prompting
strategy used in the ESM3 paper to design a novel GFP with no close natural
relatives:

1. Start from a partial sequence + a few key structural residues.
2. Use chain-of-thought generation: secondary structure → structure →
   sequence, with `entropy` unmasking strategy.
3. Filter candidates by ESMC perplexity, predicted pLDDT, and design
   target similarity.

This is the canonical "design a novel functional protein" recipe in this
repo.
