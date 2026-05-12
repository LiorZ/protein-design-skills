# Python API

Chai exposes two entry points:

| Function | Use when… |
|----------|-----------|
| `chai_lab.chai1.run_inference` | You have a FASTA file. Same surface as the CLI. |
| `chai_lab.chai1.run_folding_on_context` | You want to construct the `AllAtomFeatureContext` yourself (custom MSAs, embeddings, restraints, covalent bonds). |
| `chai_lab.batch.run_batch_inference` | You have many FASTAs in a directory and want to shard across GPUs. |

Plus the `StructureCandidates` dataclass returned by both `run_inference`
and `run_folding_on_context`.

## `run_inference`

```python
from pathlib import Path
from chai_lab.chai1 import run_inference, StructureCandidates

candidates: StructureCandidates = run_inference(
    fasta_file=Path("input.fasta"),
    output_dir=Path("out/"),
    # MSAs / templates / embeddings
    use_esm_embeddings=True,
    use_msa_server=False,                                # or True for ColabFold
    msa_server_url="https://api.colabfold.com",
    msa_directory=None,                                  # or Path("./msas")
    constraint_path=None,                                # or Path("./contacts.csv")
    use_templates_server=False,
    template_hits_path=None,                             # or Path("./hits.m8")
    # Sampling
    recycle_msa_subsample=0,
    num_trunk_recycles=3,
    num_diffn_timesteps=200,
    num_diffn_samples=5,
    num_trunk_samples=1,
    seed=42,
    device="cuda:0",
    low_memory=True,
    # IO
    fasta_names_as_cif_chains=False,
)
```

Signature notes:

- **`output_dir` must be empty or non-existent.** `run_inference`
  asserts this; pre-clean it yourself.
- Arguments after `fasta_file` and `output_dir` are **keyword-only**
  (note the `*` in the actual signature).
- Returns a `StructureCandidates` (see below).
- `num_trunk_samples > 1` writes per-trunk subdirectories
  (`trunk_0/`, `trunk_1/`, …) under `output_dir`.

## `StructureCandidates` dataclass

```python
@dataclass(frozen=True)
class StructureCandidates:
    cif_paths: list[Path]
    ranking_data: list[SampleRanking]
    msa_coverage_plot_path: Path | None
    pae: Float[Tensor, "candidate num_tokens num_tokens"]
    pde: Float[Tensor, "candidate num_tokens num_tokens"]
    plddt: Float[Tensor, "candidate num_tokens"]
```

- `cif_paths` — one CIF per diffusion sample.
- `ranking_data[i].aggregate_score` — the headline number Chai uses to
  rank candidates (higher is better).
- `pae`, `pde`, `plddt` — torch tensors, one row per candidate. PAE and
  PDE are in Å; pLDDT is on a 0–1 scale here (CIF B-factor column uses
  0–100).
- `candidates.sorted()` returns a copy sorted by `aggregate_score`
  descending.
- `StructureCandidates.concat([...])` merges multiple results, e.g. from
  separate `num_trunk_samples` runs.

`SampleRanking` (from `chai_lab.ranking.rank`) carries: `asym_ids`,
`aggregate_score`, `ptm_scores`, `clash_scores`, `plddt_scores`. The
aggregate score formula is:

```
aggregate_score = 0.2 * complex_pTM
                + 0.8 * interface_pTM
                - 100 * has_inter_chain_clashes
```

`get_scores(ranking_data)` returns a numpy dict suitable for `np.savez`
— this is what populates `scores.model_idx_*.npz`.

## Minimal scripted run

```python
import logging, shutil
from pathlib import Path
from chai_lab.chai1 import run_inference

logging.basicConfig(level=logging.INFO)

fasta = Path("/tmp/input.fasta")
fasta.write_text(""">protein|name=A
MKVLW...
>protein|name=B
GAAL
""")

out = Path("/tmp/chai_out")
if out.exists():
    shutil.rmtree(out)

result = run_inference(
    fasta_file=fasta,
    output_dir=out,
    use_msa_server=True,
    seed=0,
    device="cuda:0",
)

best = result.sorted().cif_paths[0]
print(f"Top candidate: {best}")
```

## Reading scores back

```python
import numpy as np
s = np.load("out/scores.model_idx_0.npz")
print(s["aggregate_score"], s["ptm"], s["iptm"])
print(s["per_chain_pair_iptm"])       # (n_chains, n_chains)
print(s["has_inter_chain_clashes"])   # bool
```

See [outputs.md](outputs.md) for the full schema.

## `run_folding_on_context` (advanced)

Use this when you need to construct the input context yourself —
custom MSAs that don't fit `.aligned.pqt`, custom embeddings,
hand-built restraint contexts, covalent bonds you can't express in
the FASTA + CSV pair, etc.

```python
from chai_lab.chai1 import run_folding_on_context
from chai_lab.data.dataset.all_atom_feature_context import AllAtomFeatureContext

context: AllAtomFeatureContext = build_my_context(...)
candidates = run_folding_on_context(
    context,
    output_dir=Path("out/"),
    num_trunk_recycles=3,
    num_diffn_timesteps=200,
    num_diffn_samples=5,
    seed=0,
    device=torch.device("cuda:0"),
    low_memory=True,
)
```

Helpful internal entry points:

| Function | Module |
|----------|--------|
| `make_all_atom_feature_context` | `chai_lab.chai1` — builds a context from FASTA + optional MSAs/templates/restraints |
| `load_chains_from_raw` | `chai_lab.data.dataset.inference_dataset` |
| `get_msa_contexts` | `chai_lab.data.dataset.msas.load` |
| `get_template_context` | `chai_lab.data.dataset.templates.context` |
| `get_esm_embedding_context` | `chai_lab.data.dataset.embeddings.esm` |
| `load_manual_restraints_for_chai1` | `chai_lab.data.dataset.constraints.restraint_context` |

These are exposed but **not** part of the stable API — pin your
`chai_lab` version and verify after each upgrade.

## Memory + performance knobs

| Flag | Effect |
|------|--------|
| `low_memory=True` (default) | Activations live on CPU between stages; ~2× slower, ~2× less peak VRAM. Use on 24 GB GPUs. |
| `low_memory=False` | Keep activations on GPU. Use on 48–80 GB GPUs. |
| `recycle_msa_subsample=N>0` | Subsample MSA to N rows per recycle. Helps with very deep MSAs that OOM. |
| `num_diffn_samples` | Direct VRAM cost. The diffusion module batches over samples. Drop to 1–2 for very large complexes. |
| `num_trunk_recycles` | Bigger = better trunk convergence but slower. 3 is the default; 5–10 occasionally helps. |
| `num_diffn_timesteps` | Bigger = slower, marginally better. 200 is the default; rarely worth raising. |
