# Metrics Runners — Output Columns

Every metric in `protflow.metrics.*` is a `Runner` subclass; same
`prefix` / `work_dir` / scorefile discipline as a generative runner.
This page lists what each emits.

> Convention: outputs are listed without the runner's prefix. A
> `BackboneRMSD.run(prefix="bb_rmsd", ...)` call writes `bb_rmsd_rmsd`,
> not `rmsd`.

## RMSD family — `protflow.metrics.rmsd`

### `BackboneRMSD`

```python
BackboneRMSD(ref_col=None, atoms=["CA"], chains=None, overwrite=False, jobstarter=None)
.run(poses, prefix, ref_col=None, jobstarter=None, chains=None, overwrite=False)
```

- `ref_col`: column on `poses.df` containing the reference PDB path per row.
- `atoms`: atom names to use for the RMSD (default `["CA"]`; pass
  `["N","CA","C","O"]` for backbone-heavy-atom).
- `chains`: restrict to these chains.

Columns written:

| Column                   | Meaning                  |
|--------------------------|--------------------------|
| `<prefix>_rmsd`           | RMSD value (Å)            |
| `<prefix>_description`    | Pose description          |
| `<prefix>_location`       | Pose location             |

### `AtomRMSD`

Arbitrary atom selections on both reference and query. Constructor takes
`AtomSelection` arguments; same `<prefix>_rmsd` output.

### `MotifRMSD`

```python
MotifRMSD(ref_col=None, target_motif=None, ref_motif=None, atoms=None,
          return_superimposed_poses=False, jobstarter=None, overwrite=False)
.run(poses, prefix, ...)
```

- Superimposes by `ref_motif`, computes RMSD on `target_motif`.
- `return_superimposed_poses=True`: writes aligned PDBs to
  `<work_dir>/<prefix>/aligned/` and points the `poses` column at them.

Columns: `<prefix>_rmsd`, plus the standard `_location`/`_description`.

## TM family — `protflow.metrics.tmscore`

### `TMalign`

```python
TMalign(jobstarter=None, application=None)
.run(poses, prefix, ref_col, sc_tm_score=True, options=None, pose_options=None,
     overwrite=False, jobstarter=None)
```

Columns:

| Column                           | Meaning                                         |
|----------------------------------|-------------------------------------------------|
| `<prefix>_tm_score`               | Best TM-score                                    |
| `<prefix>_tm_score_normalised`    | TM-score normalised by query length              |
| `<prefix>_aligned_length`         | Number of aligned residues                       |
| `<prefix>_rmsd`                   | RMSD over aligned region                          |
| `<prefix>_sc_tm_score`            | Single-chain TM-score (if `sc_tm_score=True`)     |

### `TMscore`

```python
TMscore(jobstarter=None, application=None)
.run(poses, prefix, ref_col, options=None, pose_options=None, overwrite=False, jobstarter=None)
```

Same flavour as TMalign; uses the TMscore binary (residue-aligned, no
sequence-independent alignment).

## DSSP — `protflow.metrics.dssp.DSSP`

```python
DSSP(jobstarter=None, application=None)
.run(poses, prefix, overwrite=False, ...)
```

| Column                              | Meaning                                              |
|-------------------------------------|------------------------------------------------------|
| `<prefix>_dssp_string`               | Full DSSP secondary-structure assignment (HBESTGI~)  |
| `<prefix>_percent_helix`             | Fraction of residues in H/G/I states                 |
| `<prefix>_percent_sheet`             | Fraction in E/B states                                |
| `<prefix>_percent_loop`              | Fraction in T/S/`~`                                   |

## Pockets — `protflow.metrics.fpocket.FPocket`

```python
FPocket(fpocket_path=None, jobstarter=None)
.run(poses, prefix, jobstarter=None, options=None, pose_options=None,
     return_full_scores=False, overwrite=False)
```

Columns (top-pocket-only by default; `return_full_scores=True` writes a
list of pocket dicts in `<prefix>_pockets`):

| Column                              | Meaning                                                      |
|-------------------------------------|--------------------------------------------------------------|
| `<prefix>_pocket_score`              | Pocket score (fpocket's own composite)                       |
| `<prefix>_druggability_score`        | 0–1, fpocket's druggability                                   |
| `<prefix>_pocket_volume`             | Å³                                                           |
| `<prefix>_pocket_residues`           | `ResidueSelection` of pocket-lining residues                 |
| `<prefix>_n_pockets`                 | Number of pockets detected                                    |

## Electrostatics — `protflow.metrics.propka.Propka`

```python
Propka(propka_path=None, options=None, jobstarter=None, overwrite=False)
.run(poses, prefix, options=None, propka_path=None, jobstarter=None, overwrite=False)
```

Columns include per-residue pKa values for titratable residues and an
overall pI. Exact column set depends on PROPKA version.

## Sequence properties — `protflow.metrics.protparam.ProtParam`

```python
ProtParam(jobstarter=None, python=None)
.run(poses, prefix, seq_col=None, pH=7, overwrite=False, jobstarter=None)
```

| Column                                            | Meaning                                |
|---------------------------------------------------|----------------------------------------|
| `<prefix>_pI`                                      | Theoretical pI                          |
| `<prefix>_molecular_weight`                        | Da                                      |
| `<prefix>_instability_index`                       | Guruprasad instability                  |
| `<prefix>_gravy`                                   | Grand average of hydropathy             |
| `<prefix>_aromaticity`                             | Lobry & Gautier                          |
| `<prefix>_charge_at_pH<pH>`                        | Net charge at the requested pH          |
| `<prefix>_extinction_coefficient_reduced`          | 280 nm ε (reduced cysteines)            |
| `<prefix>_extinction_coefficient_oxidised`         | 280 nm ε (assuming cystines)             |

If `seq_col` is None, the runner reads sequences from the active `poses`
column (PDB or fasta).

## Frame2Seq score — `protflow.metrics.frame2seqscore.Frame2SeqScore`

```python
Frame2SeqScore(python_path=None, pre_cmd=None, jobstarter=None)
.run(poses, prefix, jobstarter=None, chain="A",
     options=None, pose_options=None, preserve_original_output=False, overwrite=False)
```

Sequence-given-structure score. Outputs include `<prefix>_score` (log-likelihood
of the chain) and `<prefix>_perres_score`.

## Selection identity — `protflow.metrics.selection_identity.SelectionIdentity`

```python
SelectionIdentity(residue_selection=None, onelettercode=False, python_path=None,
                  jobstarter=None, overwrite=False)
.run(poses, prefix, residue_selection=None, onelettercode=False, ...)
```

- `residue_selection`: column name on `poses.df` holding `ResidueSelection`
  objects (or a literal selection).
- `onelettercode=True` → outputs concatenated one-letter (e.g. `'HDS'`);
  False → three-letter (e.g. `'HIS_ASP_SER'`).

Column: `<prefix>_identity`.

Use this to verify a catalytic triad survived design, or to fingerprint
interface composition.

## Ligand metrics — `protflow.metrics.ligand`

### `LigandClashes`

```python
LigandClashes(ligand_chain=None, factor=1, atoms=None, clash_distance=None,
              exclude_ligand_elements=None, jobstarter=None, overwrite=False)
.run(poses, prefix, ligand_chain=None, factor=1, clash_distance=None,
     jobstarter=None, atoms=None, exclude_ligand_elements=None, overwrite=False)
```

Counts heavy-atom clashes between `ligand_chain` and the rest of the pose.
`factor` scales the van-der-Waals sum (1.0 = vdW radius sum); pass an
explicit `clash_distance` to override.

Column: `<prefix>_n_clashes`.

### `LigandContacts`

```python
LigandContacts(ligand_chain=None, min_dist=0, max_dist=5, atoms=None,
               exclude_elements=None, jobstarter=None, overwrite=False)
.run(poses, prefix, ligand_chain=None, jobstarter=None,
     min_dist=None, max_dist=None, atoms=None, exclude_elements=None,
     normalize_by_num_atoms=True, overwrite=False)
```

Counts heavy-atom pairs between `ligand_chain` and the rest within `[min_dist,
max_dist]`. `normalize_by_num_atoms=True` divides by the ligand atom count
(useful for cross-ligand comparison).

Column: `<prefix>_n_contacts`.

## Generic biopython geometry — `protflow.metrics.biopython_metrics`

```python
from protflow.metrics.biopython_metrics import BiopythonMetricRunner, Distance, Angle

metrics = [
    Distance(name="catdist1", atoms=AtomSelection([("A",57,"NE2"), ("A",195,"OG")])),
    Distance(name="catdist2", atoms=AtomSelection([("A",102,"OD2"), ("A",195,"OG")])),
    Angle(name="catangle", atoms=AtomSelection([("A",57,"NE2"), ("A",195,"OG"), ("A",102,"OD2")])),
]
BiopythonMetricRunner(metrics=metrics).run(poses, prefix="cat")
```

Each `metric.name` becomes a column `<prefix>_<metric.name>`. Distances in
Å, angles in degrees. `distance_type="auto"` picks the right BioPython call
based on the atom shapes.

## Custom Python metrics — `protflow.metrics.generic_metric_runner.GenericMetric`

```python
GenericMetric(python_path=None, module="my_pkg.metrics", function="compute_score",
              options={"foo": "bar"}, jobstarter=None, overwrite=False)
.run(poses, prefix, ...)
```

The runner shells out to a Python process where it does
`from <module> import <function>; result = function(pose_path, **options)`.
The function must return a `dict[str, scalar]`; each key becomes
`<prefix>_<key>` on `poses.df`.

This is the escape hatch — use it before writing a full Runner subclass.
