# BioEmu examples

| File | What it is |
|------|-----------|
| `chignolin_quickstart.sh` | Runnable 30-second test: sample 100 backbones of chignolin, then summarize the ensemble (frames, RMSF, mean RMSD). |
| `recipes.md` | Copy-paste snippets for the common patterns — large ensemble, steering for long proteins, FKC RMSD targeting, BYO MSA, sub-sample then relax, ΔG_fold estimation, cryptic-pocket clustering, resume a partial run, design-then-validate cross-skill flow. |

## The shape of a BioEmu campaign

```bash
# 1. Pick a sequence (monomer only — no multimers, ligands, NAs).
# 2. Decide num_samples — 100 for exploration, 1000+ for free-energy work.
# 3. If sequence > ~100 aa, turn on physical steering.
# 4. Sample:
python -m bioemu.sample \
    --sequence <aa> --num_samples 1000 --output_dir <dir> \
    --base_seed 42 \
    [--denoiser_config src/bioemu/config/steering/physical_steering.yaml]

# 5. Optionally reconstruct side chains (sub-sample first if many frames):
python -m bioemu.sidechain_relax \
    --pdb-path <dir>/topology.pdb --xtc-path <dir>/samples.xtc \
    --outpath <dir>/relaxed

# 6. Analyze the ensemble (MDTraj / Biotite) — RMSF, clustering, ΔG_fold,
#    cryptic pocket detection, whatever you care about.
```

## Key things to remember

- **Monomers only.** No multimers, ligands, ions, DNA, RNA.
- **Backbone output.** Side chains via `bioemu.sidechain_relax`.
- **`samples.xtc` may have fewer frames than `num_samples`** when
  `filter_samples=True` (default) — long / disordered sequences lose a
  lot. Enable physical steering instead of disabling the filter.
- **`batch_size_100` scales quadratically with length.** Default 10
  works to ~200 aa on most GPUs; halve for longer sequences.
- **`base_seed` defaults to system time.** Pin it for reproducible
  ensembles.
- **Re-running resumes.** Same `output_dir` = continue from existing
  batch_*.npz.
- **Wall-clock on A100 80 GB**: ~4 min (L=100) / ~40 min (L=300) /
  ~150 min (L=600) for 1000 samples.
- **CV (FKC) steering biases the ensemble** — the result is **not**
  Boltzmann-distributed. Use only when you want to focus on a basin,
  not when you want the equilibrium ratio between basins.

## See also

- `../SKILL.md` — overview, hard limitations, output layout, gotchas.
- `../references/installation.md` — pip flavours, weights, HPacker prereqs.
- `../references/cli.md` — every `bioemu.sample` flag + Python kwarg.
- `../references/sampling.md` — model versions, batch sizing, MSA, denoisers.
- `../references/steering.md` — SMC vs FKC, YAML schema, available CVs + potentials.
- `../references/sidechain-relax.md` — HPacker + OpenMM protocols.
- `../references/outputs.md` — file layout + ensemble analysis snippets.
- `../references/troubleshooting.md` — common errors and fixes.
