# Runner Catalog

Every Runner shipped with ProtFlow, with `run()` signatures and the columns
each produces in `poses.df`. Constructor signatures all start with
`(*, jobstarter=None)` plus tool-specific overrides — those listed below are
the *additional* constructor args.

> Notation: `<prefix>_X` means the column `{prefix}_X` is added to `poses.df`
> after the runner returns.

## Backbone generation

### `protflow.tools.rfdiffusion.RFdiffusion`

```python
RFdiffusion(script_path=None, python_path=None, pre_cmd=None, jobstarter=None)

run(poses, prefix, jobstarter=None,
    num_diffusions=1, options=None, pose_options=None,
    overwrite=False, multiplex_poses=False, update_motifs=None,
    fail_on_missing_output_poses=False) -> Poses
```

- `options` / `pose_options` are RFdiffusion-style key=value strings,
  separated by spaces (regex-aware around quotes).
- `multiplex_poses=N` duplicates every input pose N× before running, then
  reindexes outputs. Use with `num_diffusions` to combine "N copies × M
  designs each".
- `update_motifs=["motif_col1", ...]` re-indexes those columns through
  `con_ref_pdb_idx → con_hal_pdb_idx` after diffusion.
- Columns: `<prefix>_plddt`, `<prefix>_perres_plddt`, `<prefix>_con_hal_pdb_idx`,
  `<prefix>_con_ref_pdb_idx`, `<prefix>_sampled_mask`, `<prefix>_input_pdb`,
  `<prefix>_description`, `<prefix>_location`.
- `index_layers = 1`.

### `protflow.tools.rfdiffusion3.RFdiffusion3`

```python
RFdiffusion3(bin_path=None, python_path=None, model_dir=None, pre_cmd=None, jobstarter=None)

run(poses, prefix, jobstarter=None,
    spec_from_json=None, spec_from_dict=None,
    num_diffusions=1, options=None, pose_options=None, overwrite=False,
    update_motifs=None, fail_on_missing_output_poses=False) -> Poses
```

- RFD3 uses an `RFD3Params` spec object (constructed from a JSON file or a
  dict). See `rfdiffusion3.py` docstring for the schema.
- Supports the same multiplexing / motif-tracking patterns as RFdiffusion.

### `protflow.tools.protein_generator.ProteinGenerator`

```python
ProteinGenerator(script_path=None, python_path=None, pre_cmd=None, jobstarter=None)

run(poses, prefix, jobstarter, options=None, pose_options=None, overwrite=False) -> RunnerOutput
```

## Sequence design

### `protflow.tools.ligandmpnn.LigandMPNN`

```python
LigandMPNN(script_path=None, python_path=None, pre_cmd=None, jobstarter=None)

run(poses, prefix, jobstarter=None,
    nseq=1, model_type=None,
    options=None, pose_options=None,
    fixed_res_col=None, design_res_col=None, pose_opt_cols=None,
    return_seq_threaded_pdbs_as_pose=False, preserve_original_output=False,
    overwrite=False) -> Poses
```

- `model_type` ∈ `{protein_mpnn, ligand_mpnn, soluble_mpnn,
  per_residue_label_membrane_mpnn, global_label_membrane_mpnn}`.
- `fixed_res_col` / `design_res_col` are convenience shortcuts that populate
  `pose_opt_cols["fixed_residues"]` / `["redesigned_residues"]`. Both expect
  `poses.df` columns of `ResidueSelection` objects.
- `pose_opt_cols={"flag_name": "df_col"}` maps LigandMPNN CLI flags to
  `poses.df` columns. The runner serialises each cell into the right CLI
  syntax.
- Columns: `<prefix>_overall_confidence`, `<prefix>_ligand_confidence`,
  `<prefix>_seq`, `<prefix>_T`, `<prefix>_seed`, `<prefix>_location`,
  `<prefix>_description`.
- `index_layers = 1`.

### `protflow.tools.frame2seqdesign.Frame2SeqDesign`

```python
Frame2SeqDesign(python_path=None, pre_cmd=None, jobstarter=None)

run(poses, prefix, jobstarter=None,
    num_samples=1, chain="A", temperature=1, options=None, pose_options=None,
    fixed_res_col=None, preserve_original_output=False, overwrite=False) -> Poses
```

### Caliby family

```python
CalibySequenceDesign(...).run(poses, prefix, nseq=1, model="caliby", ...)
CalibyEnsembleGenerator(...).run(poses, prefix, nstruct=1, options=None, cif_to_pdb=True, ...)
CalibyEnsembleSeqDesign(...).run(poses, prefix, generate_ensembles=True, gen_num_ensembles=16, ...)
```

`CalibyEnsembleSeqDesign` chains ensemble generation + ensemble-aware
sequence design. See `tools/caliby.py` for full kwargs.

## Structure prediction / validation

### `protflow.tools.esmfold.ESMFold`

```python
ESMFold(python_path=None, pre_cmd=None, jobstarter=None)

run(poses, prefix, jobstarter=None, options=None, overwrite=False, num_batches=None) -> Poses
```

- Accepts `.pdb` or `.fa/.fasta` inputs (must be uniform across the
  Poses). PDB inputs are converted via `Poses.convert_pdb_to_fasta` first.
- Columns: `<prefix>_plddt` (mean), `<prefix>_perres_plddt`,
  `<prefix>_ptm`, `<prefix>_location`, `<prefix>_description`.

### `protflow.tools.esm.ESM`

```python
ESM(python_path=None, pre_cmd=None, jobstarter=None)

run(poses, prefix, jobstarter=None,
    include=None,                              # list of score types to emit
    model="esm2_t33_650M_UR50D",
    options=None, overwrite=False) -> Poses
```

`include` ⊆ `{mean, per_tok, bos, contacts, logits, logprobs,
perres_probabilities, perres_entropy, mean_entropy}` (defaults to
`perres_entropy` when None passed at the script level).

### `protflow.tools.colabfold.Colabfold`

```python
Colabfold(script_path=None, pre_cmd=None, jobstarter=None)

run(poses, prefix, jobstarter=None, options=None, pose_options=None,
    overwrite=False, return_top_n_poses=1) -> Poses
```

- Wraps `colabfold_batch`. Columns include `<prefix>_plddt`,
  `<prefix>_ptm`, `<prefix>_iptm` (for multimers), `<prefix>_location`.
- `return_top_n_poses` keeps the top-N AF2 models per pose; lower-rank
  models are discarded.

### `protflow.tools.alphafold3.AlphaFold3`

```python
AlphaFold3(script_path=None, python_path=None, pre_cmd=None, jobstarter=None)

run(poses, prefix,
    nstruct=1, json_column=None, num_copies=1,
    msa_paired=None, msa_unpaired=None,
    templates=None, modifications=None,
    additional_entities=None,                  # ligands, DNA, RNA, ions; dict / list / column
    bonded_atom_pairs=None, user_ccd=None,
    options=None, pose_options=None,
    col_as_input=False, single_sequence_mode=False, use_templates=True,
    jobstarter=None, overwrite=False,
    return_top_n_models=1, convert_cif_to_pdb=True, random_seed=False) -> Poses
```

- `additional_entities={"ligand": {"id": "Z", "smiles": "<SMILES>"}}` adds
  a chemical entity to every pose. Pass a list of dicts for multiple
  entities. Pass `col_as_input=True` plus column names to vary entities
  per pose.
- `templates` can be a path, a list of paths, or a dict mapping chain → list
  of template specs.
- Columns: `<prefix>_ptm`, `<prefix>_iptm`, `<prefix>_ranking_score`,
  `<prefix>_chain_iptm`, etc.

### `protflow.tools.boltz.Boltz`

```python
Boltz(boltz_path=None, boltz_python=None, pre_cmd=None, jobstarter=None)

run(poses, prefix, ...) -> Poses
```

The `Boltz` runner consumes YAML inputs (see the `boltz` skill for the
schema) and produces predicted complexes + confidence JSONs. Defaults to
batching across `jobstarter.max_cores`. `index_layers = 2` (sample × model).

### `protflow.tools.minifold.Minifold`

```python
Minifold(cache_dir=None, python_path=None, pre_cmd=None, jobstarter=None)

run(poses, prefix, jobstarter=None, options=None, overwrite=False, num_batches=None) -> Poses
```

## Refinement / docking

### `protflow.tools.rosetta.Rosetta`

```python
Rosetta(script_path=None, pre_cmd=None, jobstarter=None, fail_on_missing_output_poses=False)

run(poses, prefix, jobstarter=None,
    rosetta_application=None,                   # e.g. "relax.linuxgccrelease"
    nstruct=1, options=None, pose_options=None,
    overwrite=False, fail_on_missing_output_poses=False) -> Poses
```

- `rosetta_application` is the binary inside `ROSETTA_BIN_PATH`.
- `options` / `pose_options` are passed through as Rosetta CLI flags.
- For RosettaScripts, set `rosetta_application="rosetta_scripts.linuxgccrelease"`
  and pass `-parser:protocol my_script.xml` via `options`.
- `nstruct` is forwarded to Rosetta's `-nstruct` flag; `index_layers=1`.

### `protflow.tools.attnpacker.AttnPacker`

```python
AttnPacker(python_path=None, attnpacker_dir=None, pre_cmd=None, jobstarter=None)

run(poses, prefix, jobstarter=None, overwrite=False) -> Poses
```

### `protflow.tools.placer.PLACER`

```python
PLACER(script_path=None, python_path=None, pre_cmd=None, jobstarter=None)

run(poses, prefix, nstruct=1, options=None, pose_options=None,
    jobstarter=None, overwrite=False, num_batches=None) -> Poses
```

### `protflow.tools.gnina.GNINA`

```python
GNINA(script_path=None, jobstarter=None)

run(poses, prefix, options=None, pose_options=None,
    ligand_chain=None, overwrite=False, jobstarter=None) -> Poses
```

### `protflow.tools.sigmadock.SigmaDock`

```python
SigmaDock(script_path=None, python_path=None, ckpt_path=None, pre_cmd=None, jobstarter=None)

run(poses, prefix, ...) -> Poses
```

### `protflow.tools.gromacs.Gromacs`

```python
Gromacs(gromacs_path=None, gromacs_dir=None, jobstarter=None, pre_cmd=None, md_params=None)

run(poses, prefix, jobstarter=None, n=1, t_ns=None) -> Poses
```

- `md_params` is a `MDParams(...)` object encapsulating equilibration +
  production settings.
- `n` replicates of `t_ns` ns each.

`protflow.tools.gromacs.MDAnalysis` consumes Gromacs outputs and computes
trajectory metrics.

## Edits / utilities (`protflow.tools.protein_edits`)

```python
ChainAdder(...).run(poses, prefix, jobstarter)               # add a chain
ChainRemover(...).run(poses, prefix, jobstarter=None,
                     chains=None, preserve_chains=None, overwrite=False)
SequenceAdder(sequence=None, sequence_col=None, ...).run(
    poses, prefix, jobstarter=None, sequence=None, sequence_col=None,
    insert_idx=-1, overwrite=False)
SequenceRemover(chains=None, sep=None, ...).run(
    poses, prefix, jobstarter=None, chains=None, sep=None, overwrite=False)
```

## Metrics (`protflow.metrics.*`)

### RMSD family (`protflow.metrics.rmsd`)

```python
BackboneRMSD(ref_col=None, atoms=["CA"], chains=None, overwrite=False, jobstarter=None)
   .run(poses, prefix, ref_col=None, jobstarter=None, chains=None, overwrite=False)
   # columns: <prefix>_rmsd

AtomRMSD(...).run(poses, prefix, ...)
   # arbitrary atom selections

MotifRMSD(ref_col=None, target_motif=None, ref_motif=None, atoms=None,
          return_superimposed_poses=False, jobstarter=None, overwrite=False)
   .run(poses, prefix, ...)
   # superimposes by motif; optionally returns aligned poses
```

### `protflow.metrics.tmscore`

```python
TMalign(jobstarter=None, application=None)
   .run(poses, prefix, ref_col, sc_tm_score=True, options=None, pose_options=None,
        overwrite=False, jobstarter=None)
   # columns: <prefix>_tm_score, <prefix>_sc_tm_score, etc.

TMscore(...).run(poses, prefix, ref_col, options=None, pose_options=None, ...)
```

### `protflow.metrics.dssp.DSSP`

```python
DSSP(jobstarter=None, application=None)
   .run(poses, prefix, overwrite=False, ...)
   # columns: <prefix>_dssp_string, <prefix>_percent_helix, etc.
```

### `protflow.metrics.fpocket.FPocket`

```python
FPocket(fpocket_path=None, jobstarter=None)
   .run(poses, prefix, jobstarter=None, options=None, pose_options=None,
        return_full_scores=False, overwrite=False)
   # columns: <prefix>_pocket_volume, <prefix>_druggability_score, ...
```

### `protflow.metrics.propka.Propka`

```python
Propka(propka_path=None, options=None, jobstarter=None, overwrite=False)
   .run(poses, prefix, options=None, propka_path=None, jobstarter=None, overwrite=False)
```

### `protflow.metrics.protparam.ProtParam`

```python
ProtParam(jobstarter=None, python=None)
   .run(poses, prefix, seq_col=None, pH=7, overwrite=False, jobstarter=None)
   # columns: <prefix>_pI, <prefix>_molecular_weight, <prefix>_gravy,
   #          <prefix>_instability_index, <prefix>_extinction_coefficient_reduced, ...
```

### `protflow.metrics.frame2seqscore.Frame2SeqScore`

```python
Frame2SeqScore(python_path=None, pre_cmd=None, jobstarter=None)
   .run(poses, prefix, jobstarter=None, chain="A",
        options=None, pose_options=None, preserve_original_output=False, overwrite=False)
```

### `protflow.metrics.selection_identity.SelectionIdentity`

```python
SelectionIdentity(residue_selection=None, onelettercode=False, python_path=None,
                  jobstarter=None, overwrite=False)
   .run(poses, prefix, residue_selection=None, onelettercode=False, ...)
   # columns: <prefix>_identity (concatenated residue identities of the selection)
```

### `protflow.metrics.ligand.LigandClashes`

```python
LigandClashes(ligand_chain=None, factor=1, atoms=None, clash_distance=None,
              exclude_ligand_elements=None, jobstarter=None, overwrite=False)
   .run(poses, prefix, ligand_chain=None, factor=1, clash_distance=None,
        jobstarter=None, atoms=None, exclude_ligand_elements=None, overwrite=False)
   # columns: <prefix>_n_clashes
```

### `protflow.metrics.ligand.LigandContacts`

```python
LigandContacts(ligand_chain=None, min_dist=0, max_dist=5, atoms=None,
               exclude_elements=None, jobstarter=None, overwrite=False)
   .run(poses, prefix, ligand_chain=None, jobstarter=None,
        min_dist=None, max_dist=None, atoms=None, exclude_elements=None,
        normalize_by_num_atoms=True, overwrite=False)
   # columns: <prefix>_n_contacts (optionally normalised)
```

### `protflow.metrics.biopython_metrics.BiopythonMetricRunner`

```python
BiopythonMetricRunner(metrics=[...])              # list of BiopythonMetric subclasses
   .run(poses, prefix, ...)

# Concrete metrics shipped:
Distance(name=None, atoms=AtomSelection, distance_type="auto")
Angle(name=None, atoms=AtomSelection)
```

Use this to compute custom atom-level geometry without leaving Python.

### `protflow.metrics.generic_metric_runner.GenericMetric`

```python
GenericMetric(python_path=None, module=None, function=None, options=None,
              jobstarter=None, overwrite=False)
   .run(poses, prefix, python_path=None, module=None, function=None, options=None,
        jobstarter=None, overwrite=False)
```

Runs an arbitrary `from <module> import <function>; function(pose, **options)`
across all poses. The function must return a dict of scalar scores. Use this
as the escape hatch for metrics you don't want to write a dedicated Runner
for.

## Residue selectors

These are not Runners (no `prefix` / `work_dir`); they write a single column
of `ResidueSelection` objects.

```python
ChainSelector(chain=None, chains=None).select(prefix, poses=None, chain=None, chains=None)
TrueSelector().select(prefix, poses=None)
NotSelector(residue_selection=None, contig=None).select(prefix, poses=None, ...)
DistanceSelector(center=None, distance=None, operator="<=",
                 center_atoms=None, noncenter_atoms=None, include_center=False).select(prefix, ...)
```

Each writes `{prefix}_residue_selection` to `poses.df`.
