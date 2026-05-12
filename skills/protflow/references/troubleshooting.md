# Troubleshooting

ProtFlow's failure modes cluster into a small number of patterns. This page
maps symptoms to likely causes.

## Read the appended stderr first

When a Runner raises, the exception is `Runner.CrashError` (re-wrapping the
original via `__cause__`). The message contains:

```
<RunnerClass>.collect_scores failed: <inner exception repr>

=== JOB ERROR OUTPUT ===
<last 16 KiB of the SLURM/local stderr log>
```

The job-error block is almost always the real cause. Common contents:

| Stderr says…                                  | Means                                             | Fix |
|-----------------------------------------------|---------------------------------------------------|-----|
| `CUDA out of memory`                          | GPU too small for batch/sequence                  | Reduce batch size in `options`, request a bigger GPU, or split into smaller poses. |
| `KeyError: 'protein'` / `ValueError: contig`  | Malformed Hydra contig or YAML                    | Quote contig strings; validate YAML against the tool's schema. |
| `RuntimeError: cuDNN ... initialization`      | CUDA driver/runtime mismatch                      | `module load cuda/<right_version>` in `*_PRE_CMD`. |
| `FileNotFoundError: weights/...`              | Tool can't find its model files                   | Set the tool-specific weights path; check working directory of the script. |
| `ImportError`                                 | Wrong conda env in `*_PYTHON_PATH`                | Check that the env's python is what's referenced; `conda env list`. |
| `Permission denied`                           | `*_SCRIPT_PATH` isn't executable / readable       | `chmod +x` or fix ownership. |
| `slurmstepd: error: Detected 1 oom-kill`      | Process killed by OOM-killer (memory, not VRAM)   | Bump `--mem` in `options=`. |
| `Time limit reached`                          | Walltime too short                                | Bump `--time` in `SbatchArrayJobstarter(options=...)`. |

If the stderr block is empty and you still got `CrashError`, the runner's
output-parser saw something it didn't expect — check what's actually in the
runner's `work_dir/<prefix>/`.

## ProtFlow-side errors

### `MissingConfigError`

Raised when `require_config()` can't resolve any of the four config
locations. Fix:

```bash
protflow-init-config
# or
protflow-set-config /path/to/your/config.py
# or
export PROTFLOW_CONFIG=/path/to/your/config.py
```

### `ProtFlowConfigError: Missing parameter X in config.py`

A required constant isn't *defined* in your `config.py`. Copy the matching
line from `protflow/config_template.py` and fill it in.

### `MissingConfigSettingError: Variable X not specified`

The constant exists but is empty (`""`). Set it.

### `FileNotFoundError: Path set for X does not exist at <path>`

`load_config_path` validated the path and it doesn't exist on this
filesystem. Fix the path. On shared clusters, double-check you're editing
the right file (`protflow-check-config`).

### `KeyError: Column prefix already taken in poses.df`

You called two `.run(..., prefix="foo", ...)` for the same prefix. Pick a
unique prefix or call `overwrite=True` on the existing-scores check.

### `KeyError: Could not find <col> in poses dataframe!`

You referenced a column that doesn't exist. Either:

- The step that creates it hasn't run yet.
- A typo in the column name. Note that runner output columns are prefixed:
  if you ran `prefix="esm"`, the pLDDT column is `esm_plddt`, not `plddt`.
- The column existed but was lost on a previous `Poses(...)` reload (e.g.
  `csv` round-trip lost type info).

### `ValueError: Arguments <poses> and <pose_options> ... must be of the same length`

A list `pose_options` doesn't match `len(poses)`. Common cause: you ran a
runner that fanned out poses (e.g. RFdiffusion with `multiplex_poses=N`),
then tried to apply a pre-fanout list afterwards. Rebuild
`pose_options` against the current `len(poses)`.

### `RuntimeError: Number of output poses is smaller than ...`

Some SLURM tasks crashed before producing output, and the runner was called
with `fail_on_missing_output_poses=True`. Read the appended stderr block
to find the failing tasks, fix the inputs, and re-run with `overwrite=False`
(cached scores from successful tasks will be reused).

## "I expected a fresh run but got a cached one"

ProtFlow short-circuits when `<work_dir>/<prefix>/<prefix>_scores.<storage_format>`
exists. Common causes:

- The script crashed before this step, but the previous step's score-file
  was already written from an earlier attempt.
- You re-used a `prefix` across two distinct campaigns sharing a `work_dir`.

Fix one of:

- Pass `overwrite=True` to the runner.
- Delete `<work_dir>/<prefix>/<prefix>_scores.*`.
- Change `prefix`.

## "Pipeline runs but final designs look wrong"

Mostly these:

- Composite scores have a sign error. By convention positive weight = "lower
  is better" *after normalisation*. Verify by inspecting `poses.df` before
  ranking.
- Motif column wasn't updated through RFdiffusion (`update_motifs=` not
  passed). Selection identity / fixed-residue runs then operate on the
  pre-diffusion indices — almost always wrong.
- Multiplexing not understood: `RFdiffusion(multiplex_poses=N, num_diffusions=M)`
  produces `N*M` outputs per input. If you expected only `M`, your
  filtering thresholds are calibrated wrong.
- ProtFlow short-circuit picked up stale scores from a previous campaign in
  the same `work_dir`. Always use a fresh `work_dir` for fresh campaigns.

## Loading a campaign from disk loses ResidueSelection objects

CSV / JSON serialise `ResidueSelection` to dict / string. ProtFlow
auto-rehydrates them *only* if their column name is listed in the special
`import_resselection_cols` column. To make this automatic, add the column:

```python
poses.df["import_resselection_cols"] = [["motif1", "motif2"]] * len(poses)
poses.save_scores()        # round-trip safely
```

After loading, the listed columns will be `ResidueSelection` objects again.

Alternatively, use `storage_format="pickle"` — pickles preserve object
identity exactly, no rehydration needed.

## SLURM weirdness

See `references/slurm.md`. Highlights:

- `squeue -n <jobname>` matches by name; collisions wedge the poller.
- `sacct` runs only on login nodes.
- `--open-mode=append` means stderr from multiple array tasks is
  interleaved in one file; check the merged file or override
  `options="-o ..._%a.out -e ..._%a.err"`.

## When all else fails

Inspect:

1. `<work_dir>/<prefix>/<jobname>_<ts>_cmds`: the exact commands the runner
   built. Run one manually to see what blows up.
2. `<work_dir>/<prefix>/<jobname>_<ts>_slurm.err`: full stderr (not just
   the tail).
3. `<work_dir>/<prefix>/<prefix>_scores.<format>`: the partial scores
   collected before the crash, if any.

Manually running a command from `_cmds` against a single pose is the
fastest way to diagnose tool-specific failures. The shell invocation is
exactly what SLURM ran.
