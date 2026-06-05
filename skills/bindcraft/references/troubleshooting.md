# Troubleshooting

## Install / environment

| Symptom | Cause | Fix |
|---------|-------|-----|
| `jax devices: [CpuDevice]` | CUDA mismatch | Re-run `install_bindcraft.sh --cuda <ver>` matching `nvidia-smi`. Verify with `python -c "import jax; print(jax.devices())"`. |
| `OOM during the first AF2 forward` | Target too big or GPU too small | Trim target; switch to `greedy`/`mcmc`; request a larger GPU. |
| `ModuleNotFoundError: colabdesign` or `pyrosetta` | pip step silently failed | Re-run the two `pip install` lines from `install_bindcraft.sh` manually inside the activated env. |
| `ImportError: numpy.core.multiarray` | Someone upgraded numpy to ≥ 2 | `pip install 'numpy<2'` inside the BindCraft env. |
| `params_model_5_ptm.npz: No such file` | AF2 weights download was interrupted | Delete `params/` and re-run wget + tar from the install script (or download `alphafold_params_2022-12-06.tar` manually from `https://storage.googleapis.com/alphafold/`). |

## Run-level errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| Script exits immediately with "No GPU" | `check_jax_gpu()` failed | Activate the right conda env; check `CUDA_VISIBLE_DEVICES`. |
| `FileNotFoundError: settings_target/...` | Wrong cwd | Always run from the install directory (`cd /path/to/bindcraft && python bindcraft.py ...`). Paths in JSON are resolved against the script's cwd unless absolute. |
| `KeyError: 'design_path'` in target JSON | Required key missing | The target JSON needs all 7 keys (see `inputs.md`). |
| `dalphaball_path not found` | `chmod +x` wasn't run during install | `chmod +x functions/dssp functions/DAlphaBall.gcc`. |
| `JSONDecodeError` | Trailing comma in a JSON file | JSON is strict — no trailing commas, no comments. |

## Trajectory-level failure modes

### Most trajectories land in `Trajectory/LowConfidence/`

Hallucination can't fold the binder confidently.

- Trim the target. Smaller target = fewer parameters to satisfy.
- Try a wider helicity range: `random_helicity: true`.
- Switch base preset (alpha → beta-sheet, or vice-versa).
- Raise `soft_iterations` and `temporary_iterations` by 50%.
- Try `_flexible` (mask target sequence).

### Most trajectories land in `Trajectory/Clashing/`

AF2 is squashing the binder into the target.

- Trim the target — usually the hotspot is too crowded.
- Lower the `lengths` max (e.g. `[40, 80]` instead of `[65, 150]`).
- Narrow the hotspot patch.
- Lower `inter_contact_number` from `2` to `1`.

### Trajectories pass triage but `i_pTM` / `i_pAE` filter kills everything

The binder folds in hallucination but doesn't get re-predicted as a binder.

- **Switch to `_hardtarget`** (`predict_initial_guess: true`). This is
  the single most effective rescue.
- Raise `num_recycles_validation` from `3` to `5–8`.
- For total complex > ~600 aa, also enable `predict_bigbang: true`.

### `Hotspot_RMSD` dominates the failure CSV

Binder is sliding off the intended site during reprediction.

- Use `_hardtarget`.
- Narrow the hotspot patch (smaller residue set).
- If the hotspot is right but AF2 keeps picking a *better* site
  elsewhere, accept that and let `target_hotspot_residues: null` discover it.

### `Binder_RMSD` dominates

Binder only folds when bound; AF2 doesn't predict the same fold for the
binder alone.

- Lower the `lengths` max (shorter binders are easier to fold).
- Raise `weights_plddt` (e.g. `0.15–0.2`).
- Increase `num_recycles_validation`.

### `ShapeComplementarity` / `n_InterfaceHbonds` keeps killing things

Hallucination is producing loose interfaces.

- Raise `weights_con_inter` to `1.5–2.0`.
- Lower `inter_contact_distance` from `20` to `15`.
- Use the `_mpnn` modifier so MPNN can rewire the interface.
- Consider relaxing the filter for this metric (`relaxed_filters.json`)
  — these metrics depend heavily on target chemistry; a polar target may
  cap H-bonds at 2 no matter what.

### Auto-abort triggers after `start_monitoring` trajectories

Acceptance is below `acceptance_rate`. Either:

- The settings are wrong: tune per the playbook in `advanced-settings.md`.
- The target is genuinely hard: raise `start_monitoring` to `1500–2000`,
  lower `acceptance_rate` to `0.005`, or disable the check
  (`enable_rejection_check: false`).

## "Designs look ugly"

| Symptom | Lever |
|---------|-------|
| Floppy, extended binders | Raise `weights_rg`; lower `lengths` max; tighten `intra_contact_*`. |
| All-alpha helical bundle when you wanted variety | Set `random_helicity: true` for one campaign; or run `default_*` + `betasheet_*` in parallel and merge `Accepted/`. |
| Hydrophobic surface in solution-binder mode | Raise `Surface_Hydrophobicity` threshold (lower the number, since `higher: false`); switch to `relaxed → default` filter trajectory. |
| Cysteine in the design | Set `force_reject_AA: true`; or post-filter `mpnn_design_stats.csv` for `Sequence.str.contains('C')`. |
| Designs look fine but in vitro nothing binds | This is normal — i_pTM is a binary predictor, not an affinity predictor. Order more (e.g. 20+). Validate with `boltz` + `chai-lab` (two AF3-class predictors agreeing is a stronger signal than i_pTM alone). |

## Performance

| Symptom | Lever |
|---------|-------|
| Each trajectory takes too long | Lower `num_recycles_design`; lower `num_recycles_validation`; switch to `3stage`. |
| GPU is idle between trajectories | Disk I/O bottleneck — `remove_unrelaxed_*` and `save_trajectory_pickle: false` reduce per-trajectory writes. |
| `MPNN` step is slow | Lower `num_seqs`; lower `max_mpnn_sequences`. |
| Run is on a per-job-time-limited cluster | Set `max_trajectories` to a number you can finish in walltime; re-running resumes. |

## Sanity-check snippet

```python
import pandas as pd
fail = pd.read_csv("/path/to/design_path/failure_csv.csv").T.reset_index()
fail.columns = ["metric", "count"]
print(fail.sort_values("count", ascending=False).head(15))
```

The top 5 metrics are your tuning shortlist.
