# esm-biohub examples

| File | What it does | How to run |
|------|--------------|-----------|
| `esm.def` | The upstream Apptainer/Singularity definition file (copy of `~/Repos/esm_biohub/esm.def`). Build with `apptainer build --fakeroot esm.sif esm.def` from the repo root. | `apptainer build --fakeroot "$SINGULARITY_HOME"/esm.sif esm.def` |
| `commandline_examples.sh` | Every common apptainer invocation: build, smoke-test, GPU check, HF-cache binds, pre-warm, run scripts, Jupyter, shell, GPU selection, cluster pattern. | `bash commandline_examples.sh` (skim — it has the build commented; copy-paste the lines you need) |
| `esmc_embed.py` | Minimal ESMC-300M embedding script (logits + final embeddings + mean-pooled embedding). | `apptainer exec --nv "$SINGULARITY_HOME"/esm.sif python esmc_embed.py` |
| `esmfold2_fold.py` | Fold a protein + dsDNA (modified base) + ligand complex with ESMFold2 locally; writes `1mht_pred.cif`. | `apptainer exec --nv "$SINGULARITY_HOME"/esm.sif python esmfold2_fold.py` |
| `sae_features.py` | Extract top SAE features for a sequence via the Biohub Platform; ranks layer-60 features by max activation. | `apptainer exec --nv --env ESM_API_KEY "$SINGULARITY_HOME"/esm.sif python sae_features.py` |

Most scripts assume:

```bash
export SINGULARITY_HOME=/path/to/dir/with/esm.sif
huggingface-cli login                       # for gated weights (e.g. ESMC-6B)
export ESM_API_KEY=biohub-...               # for Biohub Platform examples only
```

For more ready-made code, look at the upstream cookbook baked into the
SIF at `/opt/esm/cookbook/` (notebooks under `tutorials/`, scripts under
`snippets/`).
