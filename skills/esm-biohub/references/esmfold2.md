# ESMFold2 — structure prediction (proteins + DNA + RNA + ligands)

ESMFold2 is the AF3-class structure prediction model in this repo. It's
built on **ESMC-6B embeddings + a diffusion-based structure head** and
predicts all-atom 3D structures of complexes. State-of-the-art Foldbench
performance; validated on five therapeutic targets in the paper.

Two checkpoints:

- **Full** (`biohub/ESMFold2`, model id `esmfold2-2026-05`) — 200-step
  diffusion sampling.
- **Fast** (`esmfold2-fast-2026-05`, Biohub Platform only) — single-sequence
  mode, 32 sampling steps; ~10× faster for high-throughput screening.

The model class is `ESMFold2Model` and lives in the **EvolutionaryScale
fork of transformers** (`transformers.models.esmfold2.modeling_esmfold2`).
Plain upstream transformers does **not** have it.

## End-to-end fold call (local)

```python
from esm.models.esmfold2 import (
    DNAInput, ESMFold2InputBuilder, LigandInput,
    Modification, ProteinInput, RNAInput,
    StructurePredictionInput,
)
from transformers.models.esmfold2.modeling_esmfold2 import ESMFold2Model

# 1) Load the model
model = ESMFold2Model.from_pretrained("biohub/ESMFold2").cuda().eval()

# 2) Build the input — protein + dsDNA (modified base) + small molecule
HHAI = ("MIEIKDKQLTGLRFIDLFAGLGGFRLALESCGAECVYSNEWDKYAQEVYEMNFGEKPEGDITQVNEKTIPDH"
        "DILCAGFPCQAFSISGKQKGFEDSRGTLFFDIARIVREKKPKVVFMENVKNFASHDNGNTLEVVKNTMNELD"
        "YSFHAKVLNALDYGIPQKRERIYMICFRNDLNIQNFQFPKPFELNTFVKDLLLPDSEVEHLVIDRKDLVMTN"
        "QEIEQTTPKTVRLGIVGKGGQGERIYSTRGIAITLSAYGGGIFAKTGGYLVNGKTRKLHPRECARVMGYPDS"
        "YKVHPSTSQAYKQFGNSVVINVLQYIAYNIGSSLNFKPY")
spi = StructurePredictionInput(
    sequences=[
        ProteinInput(id="A", sequence=HHAI),
        DNAInput(id="B", sequence="GATAGCGCTATC",
                 modifications=[Modification(position=5, ccd="C36")]),
        DNAInput(id="C", sequence="TGATAGCGCTATC",
                 modifications=[Modification(position=6, ccd="C36")]),
        LigandInput(id="L", ccd=["SAH"]),
    ]
)

# 3) Fold
result = ESMFold2InputBuilder().fold(
    model, spi,
    num_loops=3, num_sampling_steps=50,
    num_diffusion_samples=1, seed=0,
)

# 4) Read out
print(f"pLDDT={result.plddt.mean():.3f} pTM={result.ptm:.3f} ipTM={result.iptm:.3f}")
open("1mht_pred.cif", "w").write(result.complex.to_mmcif())
```

## `StructurePredictionInput` schema

Definitions are in `esm.utils.structure.input_builder` and re-exported from
`esm.models.esmfold2`.

```python
@dataclass
class Modification:
    position: int                 # 0-indexed in the entity's sequence
    ccd: str                      # PDB CCD code, e.g. "C36" (5-methyl-dC)
    smiles: str | None = None     # not implemented yet

@dataclass
class ProteinInput:
    id: str | list[str]           # chain id(s) — list = homo-oligomer
    sequence: str                 # 1-letter; "|" or ":" allowed as chainbreak
    modifications: list[Modification] | None = None
    msa: MSA | None = None        # optional precomputed MSA

@dataclass
class RNAInput:
    id: str | list[str]
    sequence: str                 # 1-letter RNA
    modifications: list[Modification] | None = None

@dataclass
class DNAInput:
    id: str | list[str]
    sequence: str                 # 1-letter DNA
    modifications: list[Modification] | None = None

@dataclass
class LigandInput:
    id: str | list[str]           # chain id
    smiles: str | None = None     # provide one of smiles or ccd
    ccd: list[str] | None = None  # list of CCD codes for one ligand

@dataclass
class CovalentBond:
    chain_id1: str; res_idx1: int; atom_idx1: int   # all 0-indexed
    chain_id2: str; res_idx2: int; atom_idx2: int

@dataclass
class DistogramConditioning:
    chain_id: str
    distogram: np.ndarray         # (L, L, num_bins) soft restraint

@dataclass
class PocketConditioning:
    binder_chain_id: str
    contacts: list[tuple[str, int]]   # [(chain_id, residue_index), …]

@dataclass
class StructurePredictionInput:
    sequences: Sequence[ProteinInput | RNAInput | DNAInput | LigandInput]
    pocket: PocketConditioning | None = None
    distogram_conditioning: list[DistogramConditioning] | None = None
    covalent_bonds: list[CovalentBond] | None = None
```

Serialization helpers `serialize_structure_prediction_input` /
`deserialize_structure_prediction_input` round-trip the whole thing through
JSON-safe dicts (used by the SDK when sending to the platform).

## `ESMFold2InputBuilder.fold(...)`

```python
ESMFold2InputBuilder(ccd_cache: Path | None = None).fold(
    model: ESMFold2Model,
    input: StructurePredictionInput,
    *,
    num_loops: int = 3,             # recycling iterations
    num_sampling_steps: int = 200,  # diffusion steps (full); 32 for fast
    num_diffusion_samples: int = 1, # >1 returns a list
    seed: int | None = None,        # seeds input prep AND sampling
    noise_scale: float | None = None,
    step_scale: float | None = None,
    max_inference_sigma: int | None = None,
    early_exit: bool = False,
    complex_id: str = "pred",
) -> MolecularComplexResult | list[MolecularComplexResult]
```

- `ccd_cache` — where the Chemical Component Dictionary (CCD) is read
  from. First call downloads it; thereafter cached in `$HF_HOME/ccd` or
  similar.
- `num_loops` — recycling cycles (akin to AF3's "cycles"). 3 is the
  default; bump to 10 for the highest accuracy.
- `num_sampling_steps` — the diffusion sampler steps. 50 is a good
  speed/quality compromise; full = 200, fast = 32.
- `num_diffusion_samples` — diffusion sample diversity. >1 returns a
  list of `MolecularComplexResult` of length `num_diffusion_samples`.
- `seed` — seeds **both** input prep (SMILES → 3D conformer generation
  in rdkit) **and** the diffusion sampler. Reproducibility requires this.

The method does encode → forward → decode internally. The lower-level
`prepare_input(...)` and `decode(...)` are also exposed if you want to
batch many sequences through one tensor.

## What's behind the scenes — `clean_esmfold2_input`

This is the first step `fold` runs. It:

1. Splits `"|"`/`":"` chainbreaks in `ProteinInput.sequence` into separate
   chains.
2. Groups identical sequences into one `ProteinInput` with multiple ids
   (homo-oligomer flattening). E.g. a tetramer `["AAA|AAA|BBB|BBB"]`
   becomes `[ProteinInput(id=["0_0","0_1"], seq="AAA"),
   ProteinInput(id=["0_2","0_3"], seq="BBB")]`.
3. **Rejects** covalent bonds across a chainbreak — split those into
   explicit `ProteinInput`s first.

So you can pass either `"AAA|AAA|BBB|BBB"` or explicit chains; the result
is the same internally.

## MSA injection

```python
from esm.utils.msa import MSA

msa = MSA.from_sequences([                 # list of aligned 1-letter strings
    "MIEIKDKQLTGLRFIDLFAGLGGFRLALESCG…",
    "MIEIKEKQLTGL---DLFAGLGGFRLALESCG…",
    ...
])
ProteinInput(id="A", sequence=spi_seq, msa=msa)
```

- The first sequence in the MSA must match `ProteinInput.sequence`
  (1:1, no gaps).
- `ESMFOLD2_MAX_MSA_SEQS = 16384` is the upper bound.
- The SDK's `esmfold2_client.fold_all_atom(spi, ...)` will auto-search MSAs
  server-side if you leave them blank — set `msa=None` to opt in.

Per-chain MSAs are split automatically by `clean_esmfold2_input` when you
pass `"|"`-separated sequences.

## Covalent bonds

For inter-entity covalent bonds (e.g. glycosylation, covalent inhibitors,
disulfide cross-link between chains):

```python
from esm.models.esmfold2 import CovalentBond
spi = StructurePredictionInput(
    sequences=[
        ProteinInput(id="A", sequence="ACDE..."),
        LigandInput(id="L", smiles="CC(=O)N..."),
    ],
    covalent_bonds=[
        CovalentBond(
            chain_id1="A", res_idx1=12, atom_idx1=5,    # residue 13's CG
            chain_id2="L", res_idx2=0,  atom_idx2=3,    # atom 4 of the ligand
        ),
    ],
)
```

All indices are **0-based** (residue index and atom index within that
residue).

## Pocket / contact conditioning

The `pocket` field is a soft restraint biasing a *binder* chain toward a
list of receptor residues:

```python
from esm.utils.structure.input_builder import PocketConditioning
spi = StructurePredictionInput(
    sequences=[
        ProteinInput(id="A", sequence=target),
        ProteinInput(id="B", sequence=binder),
    ],
    pocket=PocketConditioning(
        binder_chain_id="B",
        contacts=[("A", 102), ("A", 105), ("A", 108)],   # epitope residues
    ),
)
```

## Distogram conditioning

Soft per-chain pair-distance restraints (useful for guided folding from
partial structural information, e.g. a known motif):

```python
import numpy as np
DistogramConditioning(chain_id="A", distogram=np.random.rand(L, L, 64))
```

## Result type

```python
@dataclass
class MolecularComplexResult:
    complex: MolecularComplex           # atom positions, chain info, …
    plddt: torch.Tensor | None          # per-token confidence (N_tokens,)
    ptm: float | None
    iptm: float | None
    pae: torch.Tensor | None            # (N_tokens, N_tokens)
    distogram: torch.Tensor | None      # (N_tokens, N_tokens, num_bins) logits
    pair_chains_iptm: torch.Tensor | None       # (n_chains, n_chains)
    output_embedding_sequence: torch.Tensor | None
    output_embedding_pair_pooled: torch.Tensor | None
    residue_index: torch.Tensor | None
    entity_id: torch.Tensor | None
    sae_features: np.ndarray | None
```

Serialize:

```python
mmcif_text = result.complex.to_mmcif()
pdb_text   = result.complex.to_pdb()      # via biotite under the hood
```

More on the output structures: `references/outputs.md`.

## Recipe — fold a monomer

```python
spi = StructurePredictionInput(sequences=[ProteinInput(id="A", sequence=seq)])
result = ESMFold2InputBuilder().fold(model, spi, num_loops=3, num_sampling_steps=200)
```

## Recipe — fold a homo-tetramer

```python
spi = StructurePredictionInput(sequences=[
    ProteinInput(id=["A","B","C","D"], sequence=seq),    # list of ids = oligomer
])
```

Or equivalently:

```python
spi = StructurePredictionInput(sequences=[
    ProteinInput(id="0", sequence=":".join([seq]*4)),
])
```

`clean_esmfold2_input` normalizes both.

## Recipe — protein + small molecule (CCD lookup)

```python
spi = StructurePredictionInput(sequences=[
    ProteinInput(id="A", sequence=seq),
    LigandInput(id="L", ccd=["ATP"]),               # CCD code = name3
])
```

`ccd=` is a *list* because a single ligand can be a multi-residue CCD
assembly (e.g. polysaccharides). For free-form molecules, use SMILES:

```python
LigandInput(id="L", smiles="OCCN(C)CCO")
```

The SIF carries rdkit; SMILES → 3D conformer is generated server-side.

## Recipe — protein + dsDNA

```python
spi = StructurePredictionInput(sequences=[
    ProteinInput(id="A", sequence=protein),
    DNAInput(id="B", sequence="GATAGCGCTATC"),
    DNAInput(id="C", sequence="GATAGCGCTATC"[::-1]    # complement+reverse for the other strand
                              .translate(str.maketrans("ACGT","TGCA"))),
])
```

Add `modifications=[Modification(position=5, ccd="C36")]` for a modified
base (CCD code from the RCSB chemical component dictionary).

## Multiple diffusion samples (ensemble)

```python
results = ESMFold2InputBuilder().fold(
    model, spi, num_diffusion_samples=8, seed=42,
)
for i, r in enumerate(results):
    print(i, r.iptm)
    open(f"sample_{i}.cif","w").write(r.complex.to_mmcif())
```

Returns a `list[MolecularComplexResult]` when `num_diffusion_samples > 1`.
Rank by `iptm` (multi-chain) or mean `plddt` (monomer).

## Through the Biohub Platform (no local model)

```python
import os
from esm.sdk import esmfold2_client
from esm.sdk.api import FoldingConfig
from esm.utils.structure.input_builder import ProteinInput, StructurePredictionInput

client = esmfold2_client(model="esmfold2-fast-2026-05", token=os.environ["ESM_API_KEY"])
spi = StructurePredictionInput(sequences=[ProteinInput(id="A", sequence=seq)])
cfg = FoldingConfig(num_loops=3, num_sampling_steps=32)
result = client.fold_all_atom(spi, config=cfg)
open("result.cif","w").write(result.complex.to_mmcif())
```

`FoldingConfig` is the cloud-side parameter object:

```python
@define
class FoldingConfig:
    include_distogram: bool = False
    include_pae: bool = False
    include_pair_chains_iptm: bool = False
    num_sampling_steps: int = 100
    num_loops: int = 10
    include_embeddings: bool = False
```

## Cross-validation with other AF3-class folders

ESMFold2 is one of several open AF3-class models. Cross-checking with
another (e.g. for binder design validation) is a strong signal — pair this
skill with:

- **`protenix`** (ByteDance) — see `skills/protenix/SKILL.md`.
- **`boltz`** — see `skills/boltz/SKILL.md`.
- **`chai-lab`** — see `skills/chai-lab/SKILL.md`.

A common workflow: fold with two of them, compare ipTM and pocket RMSD
with `biotite`, keep designs where both agree.
