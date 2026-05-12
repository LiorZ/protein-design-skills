# Troubleshooting

## Installation / startup

### `chai-lab: command not found`

Reinstall with `pip install chai_lab==0.6.1` and confirm with
`which chai-lab`. If installed inside a venv, activate it.

### `ModuleNotFoundError: No module named 'chai_lab'`

You installed `chai-lab` (with hyphen) — the **import name** is
`chai_lab` (underscore). Both `import chai_lab` and `pip install
chai_lab` should work; the CLI is `chai-lab` only because Python
script names allow hyphens.

### Slow first run; "Downloading…"

Expected. Chai downloads ~25 GB of TorchScript components and ESM-2
weights to `<site-packages>/chai_lab/downloads/`. Set
`CHAI_DOWNLOADS_DIR=/some/persistent/path` if you don't want to re-do
this in containers.

### `torch.cuda.OutOfMemoryError` on import / first forward

You loaded the model on a too-small GPU. Try a GPU ≥24 GB. If you only
have 24 GB, keep `low_memory=True` (default) and shrink your input.

## Input validation errors

### `UnsupportedInputError: Too many tokens in input: N > 2048`

Your complex is too big. Options:

- Truncate disordered tails or flexible linkers.
- Split into smaller sub-complexes.
- Crop a large ligand to a fragment (ligands are per-atom tokenised).

### `entity_name used more than once in inputs`

Two FASTA records share the same `name=`. Give every entity a unique
name.

### `Provided sequence is likely DNA, not PROTEIN` (warning)

You wrote an `ACGT` string under `>protein|…`. Either fix the header to
`>dna|…` or ignore if you really do mean a protein made only of
Ala-Cys-Gly-Thr.

### `Discrepant tokens in input and MSA`

The MSA loaded for a chain has a different sequence than the one in
the FASTA. The `.aligned.pqt` filename is determined by sequence hash;
make sure you (re)generate the MSA whenever you change the sequence.

### `Output directory <X> is not empty`

`run_inference` refuses to overwrite. Delete the directory or pick a
new one. In scripts:

```python
import shutil
if out.exists():
    shutil.rmtree(out)
```

### `Too many templates in input: N > 4`

The cap is 4 templates per chain. Reduce `.m8` rows.

### `MSA too deep: N > 16384`

Sub-sample your MSA, or set `recycle_msa_subsample=2048` (Chai will
sample that many rows per recycle).

## CUDA / VRAM issues

### `torch.cuda.OutOfMemoryError` during the trunk or diffusion stage

In order of cheapness:

1. Make sure `low_memory=True` (the default).
2. Drop `num_diffn_samples` from 5 → 2 → 1.
3. Set `recycle_msa_subsample` to a small value (1024 or 512).
4. Shorten the input (especially long flexible regions or oversized
   ligands).
5. Move to a bigger GPU.

### Multi-GPU "doesn't work"

There is **no within-fold model parallelism**. Use `chai-lab fold-batch`
for multi-GPU — one fasta per worker per GPU.

## MSA / template issues

### ColabFold server is slow / times out

The public `api.colabfold.com` is shared and rate-limited. Options:

- Host your own ColabFold MSA server and pass
  `--msa-server-url <URL>`.
- Precompute MSAs once and use `--msa-directory`.
- Run during off-peak hours.

### Templates seem ignored

Common causes:

- The query name in the `.m8` doesn't match a FASTA entity name (when
  using `--template-hits-path`).
- The CIF for an identifier can't be downloaded from RCSB (rate-
  limited or removed). Provide local cifs via
  `CHAI_TEMPLATE_CIF_FOLDER`.
- More than 4 templates listed → only the first 4 are loaded.

## Restraint issues

### `Provided residue X does not match input sequence`

The `res_idxA` / `res_idxB` value (e.g. `D4`) names a residue that
doesn't match the FASTA at that 1-based index. Likely an off-by-one or
typo in either the restraint file or the sequence.

### Restraint doesn't change the prediction

Restraints are **biases**, not hard constraints. If Chai's prior is
strong enough, weak restraints get ignored. Try:

- Tighter `max_distance_angstrom` (e.g. 5.5 Å instead of 12 Å).
- More restraints (a small set of contacts is more informative than
  pockets).
- Check the chain letter — `chainA=A,B,C…` follows FASTA order, not
  entity name (unless `--fasta-names-as-cif-chains` is set).

### Covalent bond doesn't show in output CIF

Verify the atom names. The `@N` / `@SG` / `@C1` suffixes must match
the actual atom labels:

- For amino acids: standard PDB nomenclature (`N`, `CA`, `C`, `O`,
  `CB`, `OG`, `SG`, …).
- For sugar CCD codes: standard glycan ring naming (`C1`, `O4`, …).
- For SMILES ligands: RDKit's auto-assigned names — build the molecule
  with the same RDKit version and inspect.

## Performance is worse than expected

- **No MSAs** for naturally-occurring proteins → significant accuracy
  drop. Add `--use-msa-server`.
- **MSAs but no templates** for a target with close PDB homologs →
  add `--use-templates-server`.
- **Stochastic** — try multiple seeds (`--seed 0`, `1`, `2`) and
  higher `--num-trunk-samples`. Real complexes occasionally need 10+
  samples to find the right pose.
- **Designed binder + MSA-on** → MSA pairing logic is unhelpful with a
  novel sequence; use single-sequence mode.
- **Big flexible target** → consider folding only the relevant domain
  and using restraints to keep the binder near the epitope.

## Reproducibility

Setting `seed=N` should give identical predictions across runs **on
the same GPU model and same chai_lab version**. Different GPU models
(A100 vs H100) can produce numerically different results due to
fused-kernel implementations. Pin both `chai_lab` and GPU type for
exact reproduction.

## Where to file bugs

Open a GitHub issue at
https://github.com/chaidiscovery/chai-lab/issues with: chai_lab
version (`pip show chai_lab`), GPU model, full FASTA input, full
command line, and the traceback.
