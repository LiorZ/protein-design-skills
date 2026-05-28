# Outputs — `ESMProtein`, `MolecularComplex`, confidence scores

ESM emits two canonical container types depending on the task:

- **`ESMProtein`** — used by ESMC (when going through the SDK) and by
  ESM3. Single-protein-centric with optional structure / SSE / SASA /
  function tracks. PDB + biotite-friendly.
- **`MolecularComplex(Result)`** — used by ESMFold2. Multi-entity
  (protein + nucleic acid + ligand) all-atom complex with mmCIF output.

Plus a handful of internal dataclasses (`ESMProteinTensor`,
`MolecularComplexMetadata`, `Molecule`) that you mostly see only when
debugging.

## `ESMProtein`

Full field list (from `esm.sdk.api`):

```python
@define
class ESMProtein(ProteinType):
    # Tracks
    sequence: str | None
    secondary_structure: str | None          # 1-letter SSE  (H/E/C…)
    sasa: list[float | None] | None          # per-residue
    function_annotations: list[FunctionAnnotation] | None
    coordinates: torch.Tensor | None         # (L, 37, 3) atom37

    # Metrics
    plddt: torch.Tensor | None               # (L,)
    ptm: torch.Tensor | None                 # scalar
    pae: torch.Tensor | None                 # (L, L)

    # Multi-chain / complex extras (filled by ESM3 batch flows)
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

`__len__` returns the length of the first available track in the order
`sequence → secondary_structure → sasa → coordinates`. So
`len(protein)` works on a coords-only or SSE-only `ESMProtein` too.

### I/O

```python
ESMProtein.from_pdb("x.pdb")                # all chains
ESMProtein.from_pdb("x.pdb", chain_id="A")  # one chain
ESMProtein.from_pdb("x.pdb", chain_id="detect", is_predicted=True)
ESMProtein.from_protein_chain(chain)
ESMProtein.from_protein_complex(pc)

protein.to_pdb("out.pdb")
protein.to_pdb_string()                     # returns text
protein.to_protein_chain()                  # → biotite-backed ProteinChain
protein.to_protein_complex()                # → multi-chain ProteinComplex
protein.copy()                              # deep copy
```

`is_predicted=True` reads B-factors as the confidence track (so an AF /
ESMFold output PDB round-trips with `plddt`).

For multi-chain complexes, `sequence` uses **`|`** as the chain separator
(`"MKT...|ACD...|..."`).

### Confidence interpretation

| Field | Range | Higher = | Use when |
|-------|-------|----------|---------|
| `plddt` | 0-1 (sometimes 0-100, depending on source) | better | Per-residue confidence. Mean over the chain is a useful summary. |
| `ptm` | 0-1 | better | Global predicted TM-score |
| `pae` | Å (lower = better) | — | Pair-wise predicted aligned error |
| `pair_chains_iptm` | 0-1 (per chain pair) | better | Multi-chain interface quality, per pair |
| `interface_ptm` | 0-1 | better | Single pooled interface score |

ESM3 typically returns `plddt` and `ptm`; ESM3 complex flows fill
`interface_ptm` and `pair_chains_iptm`. ESMFold2 returns these via
`MolecularComplexResult` instead (see below).

## `ESMProteinTensor`

The token-space twin of `ESMProtein` — every track is an `int64` tensor
plus an optional `coordinates` float tensor:

```python
@define
class ESMProteinTensor(ProteinType):
    sequence: torch.Tensor | None
    structure: torch.Tensor | None           # structure tokens (4096 codes)
    secondary_structure: torch.Tensor | None
    sasa: torch.Tensor | None
    function: torch.Tensor | None
    residue_annotations: torch.Tensor | None
    coordinates: torch.Tensor | None
    potential_sequence_of_concern: bool = False
```

Used as the intermediate between `client.encode` and `client.decode`. The
helpful methods are `.to(device_or_dtype)` and
`ESMProteinTensor.empty(length=...)` (empty placeholders with default
mask tokens).

## `ESMProteinError`

```python
@define
class ESMProteinError(Exception, ProteinType):
    error_code: int       # HTTP-like
    error_msg: str
```

Returned (not raised) by SDK methods on per-call failures. Always
type-check: `isinstance(x, ESMProtein) / isinstance(x, ESMProteinError)`.

## `MolecularComplexResult` (ESMFold2)

```python
@dataclass
class MolecularComplexResult:
    complex: MolecularComplex
    plddt: torch.Tensor | None              # (N_tokens,)
    ptm: float | None
    iptm: float | None
    pae: torch.Tensor | None                # (N_tokens, N_tokens)
    distogram: torch.Tensor | None          # (N_tokens, N_tokens, num_bins) logits
    pair_chains_iptm: torch.Tensor | None   # (n_chains, n_chains)
    output_embedding_sequence: torch.Tensor | None
    output_embedding_pair_pooled: torch.Tensor | None
    residue_index: torch.Tensor | None
    entity_id: torch.Tensor | None
    sae_features: np.ndarray | None         # [L, n_features] if SAE was attached
```

This is what `ESMFold2InputBuilder.fold(...)` returns.

### `MolecularComplex` — the structure container

```python
@dataclass(frozen=True)
class MolecularComplex:
    id: str
    sequence: list[str]                  # token list, e.g. ['MET', 'LYS', 'A', 'G', 'ATP']

    atom_positions: np.ndarray           # (N_atoms, 3) XYZ
    atom_elements: np.ndarray            # (N_atoms,)  element symbols
    token_to_atoms: np.ndarray           # (N_tokens, 2) start/end indices

    chain_id: np.ndarray                 # (N_tokens,) chain per token
    plddt: np.ndarray                    # (N_tokens,) per-token confidence

    metadata: MolecularComplexMetadata
```

`MolecularComplexMetadata` carries `entity_lookup`, `chain_lookup` and
optionally `assembly_composition`.

### Serializing a `MolecularComplex`

```python
mmcif_text = result.complex.to_mmcif()   # uses biotite under the hood
pdb_text   = result.complex.to_pdb()
open("out.cif","w").write(mmcif_text)
```

mmCIF is the **preferred** format for ESMFold2 outputs because it can
represent ligand atoms, chains beyond A-Z, and modifications cleanly. PDB
loses some of that.

### Iterating atoms / tokens

```python
mc = result.complex
for token_idx in range(len(mc.sequence)):
    start, end = mc.token_to_atoms[token_idx]
    atoms = mc.atom_positions[start:end]            # (n_atoms_this_token, 3)
    elements = mc.atom_elements[start:end]
    chain = mc.chain_id[token_idx]
    conf  = mc.plddt[token_idx]
```

### Confidence interpretation for ESMFold2

| Score | Range | Higher = | Notes |
|-------|-------|----------|-------|
| `plddt` (per-token) | 0-1 | better | Mean is the chain-level confidence summary |
| `ptm` | 0-1 | better | Global predicted TM-score |
| `iptm` | 0-1 | better | Interface predicted TM-score — multi-chain complexes |
| `pair_chains_iptm` | 0-1 (per pair) | better | Identifies which interface is weak in a 3+ chain complex |
| `pae` | Å | lower | Predicted aligned error map; bins for distant residue pairs that the model is uncertain about |

For binder design, **`iptm > 0.5`** is the rule-of-thumb survival
threshold (similar to AF-Multimer / AF3). For monomeric folds, **mean
`plddt > 0.7`** is the equivalent. Use `pair_chains_iptm` to triage
3+-chain complexes: a high `iptm` can mask a bad single interface.

## `ForwardTrackData` (ESM3 / ESMC logits)

What `LogitsOutput.logits` looks like:

```python
@define
class ForwardTrackData:
    sequence: torch.Tensor | None            # (B, L+2, V_seq)
    structure: torch.Tensor | None
    secondary_structure: torch.Tensor | None
    sasa: torch.Tensor | None
    function: torch.Tensor | None
```

Each tensor is `(batch, length+2 (BOS/EOS), vocab)`. Indexed by track
name so you don't need to know which dim is what.

## `LogitsOutput`

```python
@define
class LogitsOutput:
    logits: ForwardTrackData | None
    embeddings: torch.Tensor | None
    mean_embedding: torch.Tensor | None
    residue_annotation_logits: torch.Tensor | None   # multi-hot (Bernoulli)
    hidden_states: torch.Tensor | None               # single layer
    mean_hidden_state: torch.Tensor | None
    sae_outputs: dict[str, torch.Tensor] | None
```

What's populated depends on the `LogitsConfig` you passed (see
`references/esmc.md`).

## `ForwardAndSampleOutput` — extra sampling diagnostics

```python
@define
class ForwardAndSampleOutput(LogitsOutput):
    protein_tensor: ESMProteinTensor         # the sampled state
    entropy: ForwardTrackData | None         # per-token entropy
    prob: ForwardTrackData | None            # probability of the sampled token
    logprob: ForwardTrackData | None
    top_prob: ForwardTrackData | None
    topk_logprob: ForwardTrackData | None
    topk_tokens: ForwardTrackData | None
    per_residue_embedding: torch.Tensor | None
    mean_embedding: torch.Tensor | None
```

Returned by `client.forward_and_sample(...)`. Useful when you need to
inspect alternatives (`topk_tokens`) or rank generations by confidence
(`mean(prob)` over the sampled track).

## How to choose a "best" sample

For a batch of ESMFold2 samples:

```python
ranked = sorted(results, key=lambda r: r.iptm, reverse=True)    # multi-chain
ranked = sorted(results, key=lambda r: r.plddt.mean().item(), reverse=True)  # monomer
best = ranked[0]
open("best.cif","w").write(best.complex.to_mmcif())
```

For a batch of ESM3 generations (`batch_generate`):

```python
proteins = client.batch_generate(prompts, configs)
keep = [p for p in proteins if isinstance(p, ESMProtein)]
keep.sort(key=lambda p: float(p.ptm), reverse=True)
```

## Round-tripping into biotite for downstream analysis

```python
import biotite.structure.io.pdbx as pdbx
from io import StringIO

cif = result.complex.to_mmcif()
atoms = pdbx.get_structure(pdbx.CIFFile.read(StringIO(cif)), model=1)
# Now use biotite's RMSD / lDDT / SASA / TM-score / SSE helpers
```

The `biotite` skill (`skills/biotite/SKILL.md` in this repo) has the
canonical recipes for these metrics.
