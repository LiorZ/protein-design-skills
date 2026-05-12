# invrotzyme CLI — every flag with worked examples

Source of truth: `invrotzyme.py` argparse block (lines 430–460).

## Invocation

```bash
python /path/to/invrotzyme.py --cstfile <FILE> [flags...]
```

Imports work as long as `invrotzyme.py` is invoked by path — it adds
its own directory and `utils/` to `sys.path`.

## Required

| Flag | Default | Description |
|------|---------|-------------|
| `--cstfile FILE` | — | Rosetta matcher/enzdes CST file. Six DOFs per block required. |

## Input files

| Flag | Default | Description |
|------|---------|-------------|
| `--params FILE [FILE ...]` | — | One `.params` per non-canonical residue / ligand. Joined into PyRosetta's `-extra_res_fa`. |
| `--motif_for_cst CSTNO:RESNO:PATH [...]` | — | Per-CST external motif PDB. **Only `CSTNO=1` works** (asserted in `parse_motif_input`). |

## Rotamer filtering

| Flag | Default | Description |
|------|---------|-------------|
| `--dunbrack_prob FLOAT` | `0.85` | Cumulative Dunbrack probability cutoff (lower = stricter). |
| `--dunbrack_prob_per_cst F [F ...]` | — | Per-CST override (ligand-excluded list). |
| `--keep_his_tautomer 'CST:HIS,CST:HIS_D'` | — | Pin a HIS tautomer per CST. Strings must be `HIS` or `HIS_D`. |
| `--use_best_rotamer_cstids N [N ...]` | `[]` | For these CST IDs (1-indexed), only the single best rotamer per secondary-structure bin is kept. Auto-sets the corresponding `frac_random_rotamers_per_cst[N]` to `1.0`. |

## Random subsampling

These are mutually exclusive only in the sense that the last one wins
(both `max_*` and `frac_*` can be set, but the per-CST forms override
the scalar forms).

| Flag | Description |
|------|-------------|
| `--max_random_rotamers N` | Same N applied to all residues. |
| `--max_random_rotamers_per_cst N0 N1 N2 ...` | Per-CST cap, **N0 is the ligand**. Must match `len(restypes)+1`. |
| `--frac_random_rotamers FLOAT` | Same fraction (0–1) for all residues. |
| `--frac_random_rotamers_per_cst F0 F1 F2 ...` | Per-CST fraction, **F0 is the ligand**. Must match `len(restypes)+1`. |
| `--prune_ligand_rotamers FLOAT` | RMSD cutoff (Å) for ligand-rotamer dedup. `0.0` disables. |

## Backbone stub generation

| Flag | Default | Description |
|------|---------|-------------|
| `--secstruct H\|E` | `H` | Idealized secondary structure for all stubs. |
| `--secstruct_per_cst S [S ...]` | — | Per-CST override (`E`, `H`, `-`). Length = number of CSTs (ligand-excluded). |
| `--N_len N` | `4` | Residues N-terminal of each catalytic residue. |
| `--C_len N` | `5` | Residues C-terminal of each catalytic residue. |
| `--N_len_per_cst N [N ...]` | — | Per-CST override. |
| `--C_len_per_cst N [N ...]` | — | Per-CST override. |

Setting `--N_len 0 --C_len 0` produces no stub — only the rotamer
sidechain is emitted. Useful when the downstream pipeline (e.g.
RFdiffusionAA) will build its own backbone.

## Extra χ sub-sampling

| Flag | Description |
|------|-------------|
| `--extra_chi 'CHI:LEVEL,CHI2:LEVEL2'` | Apply to all CSTs. Levels per `calculate_samplings`. |
| `--extra_chi_per_cst 'CST-CHI:LEVEL' [...]` | Per-CST. Format: `<cstno>-<chi>:<level>,<chi2>:<level2>`. |

Levels:

| Level | Samples |
|-------|---------|
| 0 | original only |
| 1 | ± 1 σ — 3 |
| 2 | ± 0.5 σ — 3 |
| 3 | ± 1 σ, 2 σ — 5 |
| 4 | ± 0.5 σ, 1 σ — 5 |
| 5 | ± 0.5, 1, 1.5, 2 σ — 9 |
| 6 | ± 0.33, 0.67, 1 σ — 7 |
| 7 | ± 0.25, 0.5, 0.75, 1, 1.25, 1.5 σ — 13 |

## Output / runtime

| Flag | Default | Description |
|------|---------|-------------|
| `--prefix STR` | `""` | Prepended to every output filename. Use `outputs/` to redirect. |
| `--suffix STR` | `""` | Appended (before `.pdb`). Internally formatted as `_<suffix>`. |
| `--tip_atom` | off | Skip pairwise clash analysis. Pre-select by unique tip-atom placement. |
| `--nproc N` | `os.cpu_count()` | CPU cores. **Overridden by `SLURM_CPUS_ON_NODE`** if set. Forced to 1 under `--debug`. |
| `--max_outputs N` | — | Early-stop after N PDBs are written. Sets a shared multiprocessing flag. |
| `--debug` | off | Single-threaded + verbose printing. |

## Worked examples

### Kemp eliminase (3 CSTs, 0.5 fraction, HHE)

```bash
python invrotzyme.py \
  --cstfile inputs/BIO_His_ED_oxy_nosample.cst \
  --params  inputs/BIO.params \
  --dunbrack_prob 0.6 \
  --frac_random_rotamers_per_cst 0.5 0.5 0.5 0.5 \
  --secstruct_per_cst H H E \
  --prefix outputs/ \
  --suffix HHE
```

- 3 CSTs → 4 fractions (ligand-first), 3 secondary structures
  (ligand-excluded).
- Dunbrack 0.6 is aggressive — favors high-probability rotamers.

### P450 with external motif on CST 1

```bash
python invrotzyme.py \
  --cstfile inputs/HBA_CYS_P450_nosample.cst \
  --params  inputs/HBA_unique.params \
  --motif_for_cst 1:3:inputs/P450_motif.pdb \
  --frac_random_rotamers 0.1 \
  --prefix outputs/
```

- Residue 3 of `P450_motif.pdb` is fixed in CST 1; other CSTs enumerate
  normally.
- Scalar `--frac_random_rotamers 0.1` applies to all residues (10%
  random pick).

### Pin HIS tautomer + cap outputs

```bash
python invrotzyme.py \
  --cstfile  example.cst \
  --params   lig.params \
  --keep_his_tautomer '1:HIS' \
  --dunbrack_prob 0.5 \
  --use_best_rotamer_cstids 2 3 \
  --max_outputs 500
```

- CST 1's HIS pinned to standard tautomer (no HIS_D).
- CSTs 2 and 3 reduced to one rotamer per SS bin.
- Stop after 500 good assemblies.

### Maximum diversity (no stubs, tip-atom mode)

```bash
python invrotzyme.py \
  --cstfile rich.cst \
  --params  lig.params \
  --N_len 0 --C_len 0 \
  --tip_atom \
  --dunbrack_prob 0.9
```

Use this when you want geometric diversity of catalytic placements
without backbone stubs — appropriate as an *input enumeration* for
RFdiffusionAA when the diffusion model is responsible for the
scaffold.

### Extra χ sub-sampling on CST 2 only

```bash
python invrotzyme.py \
  --cstfile  example.cst \
  --params   lig.params \
  --extra_chi_per_cst '2-1:1,2:1' \
  --frac_random_rotamers_per_cst 0.3 1.0 0.3 1.0
```

- CST 2's χ1 and χ2 each sub-sampled at ±1σ (3 samples).
- The other CSTs are 30%-random-subsampled to control the explosion
  caused by the extra-χ widening on CST 2.

## SLURM submission shape

```bash
#!/bin/bash
#SBATCH -c 32
#SBATCH --mem 16G
#SBATCH -t 0-4:00
source ~/anaconda3/etc/profile.d/conda.sh
conda activate pyrosetta-env
cd $SLURM_SUBMIT_DIR
python /path/to/invrotzyme.py \
  --cstfile     my.cst \
  --params      lig.params \
  --dunbrack_prob 0.6 \
  --frac_random_rotamers_per_cst 0.4 0.4 0.4 0.4 \
  --prefix      outputs/run1_
```

`SLURM_CPUS_ON_NODE` is read automatically (overriding any `--nproc`
you pass). The process is CPU-bound; no GPU allocation required.
