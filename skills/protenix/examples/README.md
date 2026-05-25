# Protenix examples

Runnable starting points for the `protenix` skill. The canonical Apptainer setup
lives in the Protenix repo at `~/Repos/Protenix/apptainer/` — these examples
drive it.

## Files

- **`run_examples.sh`** — copy-paste `apptainer/run_protenix.sh` invocations:
  monomer, multi-job, screening, templates, constraints, single-sequence, input
  prep (`json`/`msa`/`mt`/`prep`), CPU-prep + GPU-predict split, and a manual
  `apptainer run` with GPU pinning.
- **`input_examples.md`** — input JSON snippets (protein, oligomer,
  protein+ligand+ion, dsDNA, PTMs, covalent bonds, MSA/template paths, pocket and
  contact constraints).

## One-time setup

```bash
cd ~/Repos/Protenix
bash apptainer/build.sh                                              # build protenix.sif (--fakeroot)
PROTENIX_ROOT_DIR=/shared/ModelWeights/Protenix bash apptainer/download_weights.sh
```

## Run your own structure

```bash
cd ~/Repos/Protenix

# A) Already have an input JSON (see input_examples.md):
apptainer/run_protenix.sh pred -i /abs/path/my_job.json -o ./out \
    -n protenix_base_default_v1.0.0 --use_default_params true

# B) Start from an experimental structure -> JSON -> predict:
apptainer/run_protenix.sh json -i /abs/path/complex.cif -o ./jsons
apptainer/run_protenix.sh pred -i ./jsons/complex.json -o ./out \
    -n protenix_base_default_v1.0.0 --use_default_params true
```

Output per job: `out/<name>/<seed>/<name>_<seed>_sample_*.cif` plus
`..._summary_confidence_sample_*.json`. Rank samples by **`ranking_score`**.

## Key reminders

- **`--nv` is required** for the GPU — the wrapper adds it; add it yourself to
  manual `apptainer run`/`exec` commands.
- **Weights are host-side**, bind-mounted via `PROTENIX_ROOT_DIR` — not in the
  image. Download them once.
- **`--use_default_params true`** sets the right cycle/step per model.
- **Templates / RNA MSA** only on `protenix_base_default_v1.0.0`,
  `protenix_base_20250630_v1.0.0`, `protenix-v2`; **constraints** only on
  `protenix_base_constraint_v0.5.0`.
- Run from a **data directory**, not a Protenix checkout, so cwd doesn't shadow
  the baked-in source (see `../references/installation.md`).

See `../SKILL.md` for the overview and `../references/` for full CLI, inputs,
models, outputs, and troubleshooting docs.
</content>
