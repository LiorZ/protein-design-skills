# Example Scripts

Five runnable pipelines that exercise the most common ProtFlow patterns.
All can be invoked as plain Python scripts (`python <script>.py --help`).

| File                                       | What it builds                                                                       |
|--------------------------------------------|--------------------------------------------------------------------------------------|
| `minimal_pipeline.py`                      | Load PDBs → DSSP → ProtParam → filter on instability → save.                          |
| `rfdiffusion_mpnn_esm.py`                  | De novo monomers: RFdiffusion → SolubleMPNN → ESMFold → BB-RMSD self-consistency.    |
| `binder_design_rfdiff_validate.py`         | Binder design: hotspot RFdiffusion → LigandMPNN → AF2/AF3 ipTM → composite ranking.  |
| `predict_protein_ligand.py`                | High-throughput AlphaFold3 protein-ligand co-folding from a list of FASTAs + a SMILES. |
| `enzyme_redesign.py`                       | Active-site fixed, pocket designed: pocket selection → LigandMPNN → Rosetta relax → identity check. |

## Running them

All scripts assume:

- ProtFlow is installed and `config.py` is set up.
- A working SLURM cluster *or* a local GPU (use `--local` to swap to `LocalJobStarter`).
- An empty `--out_dir` (or pass `--overwrite`).

For a no-cluster smoke test, every script accepts `--local` and falls back
to `LocalJobStarter`. Most of the tools you'd invoke (RFdiffusion, ESMFold,
AlphaFold3) still need a GPU, so you'll need at least a single accessible
NVIDIA card.

## Adapting them

The general pattern in every script is the same:

```python
poses = Poses(...).set_jobstarter(...)          # load inputs
for step, runner, prefix, kwargs in pipeline:
    poses = runner.run(poses, prefix=prefix, **kwargs)
poses.filter_poses_by_value(...)
poses.filter_poses_by_rank(...)
poses.calculate_composite_score(...)
poses.save_scores(); poses.save_poses(...)
```

To adapt: change the list of `(runner, prefix, kwargs)` tuples to whatever
pipeline you want. ProtFlow's score-file caching means rerunning the script
after fixing a downstream step re-executes only the broken step.
