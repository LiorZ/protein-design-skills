# SLURM Cluster Tips

ProtFlow's SLURM backend (`SbatchArrayJobstarter`) is intentionally thin —
it builds an `sbatch -a 1-N%C` array, writes a cmd file, and polls
`squeue -n <jobname>`. The cluster-side wrinkles below catch most users.

## Array size cap

`SbatchArrayJobstarter.slurm_max_arrayjobs` defaults to `1000`. If your
cluster sets `MaxArraySize=10000` (or whatever), set:

```python
js = SbatchArrayJobstarter(...)
js.slurm_max_arrayjobs = 5000
```

Beyond that, ProtFlow recursively splits the cmd list into multiple
arrays. Each chunk is a separate `sbatch` submission with the same jobname;
the poll-loop waits for all of them.

## Job name collisions

`squeue -n <jobname>` matches by name, not by JobID. If a previous run left
a job hanging with the same `prefix`, the new submission will *appear* to
"wait for itself" indefinitely. Mitigations:

- `add_timestamp(jobname)` is called by the runner, so every fresh
  submission has a unique suffix. You only see collisions when two ProtFlow
  scripts share the same prefix at the same instant.
- If `squeue` is slow on your cluster, the 5-second poll multiplied across
  dozens of prefixes can dominate runtime. Bump `interval=` in
  `wait_for_job(jobname, interval=...)` by subclassing if needed.

## `sacct` is login-node only

`get_SLURM_stats` shells out to `sacct`. Compute nodes typically don't have
`sacct` in PATH. Run any post-processing that needs accounting numbers from
the same login node where you submitted.

Pass `start_time` to scope the query:

```python
import datetime as dt
from protflow.jobstarters import get_SLURM_stats

session_start = dt.datetime.now().isoformat(timespec="seconds")
# ... submit jobs ...
stats = get_SLURM_stats(js.last_job_name, start_time=session_start)
```

Without `start_time`, `sacct` returns *every* job with that name ever, which
is usually wrong.

## Per-task output / error files

Every array job writes:

```
<work_dir>/<prefix>/<jobname>_<ts>_slurm.out   # stdout
<work_dir>/<prefix>/<jobname>_<ts>_slurm.err   # stderr
```

These are **merged** across all array tasks (`--open-mode=append`). To find
which task failed:

```bash
grep "^slurmstepd" <work_dir>/<prefix>/<jobname>_*_slurm.err
```

For per-task files, modify `SbatchArrayJobstarter.options` to include
`-o <jobname>_%A_%a.out -e <jobname>_%A_%a.err`. ProtFlow's stderr-tail
capture mechanism reads the merged file, so it still picks up the last
errors regardless.

## GPU requests

`SbatchArrayJobstarter(gpus=1)` adds `--gpus-per-node 1`. If your cluster
uses `--gres=gpu:1` instead, override `options=`:

```python
SbatchArrayJobstarter(max_cores=10, gpus=False,
                       options="--gres=gpu:1 --partition=gpu --time=08:00:00")
```

The `gpus=` flag is shorthand only; nothing stops you from constructing the
sbatch flags by hand.

## Common partition / QoS patterns

```python
# Short / debug
sbatch_debug = SbatchArrayJobstarter(max_cores=4, options="--time=00:30:00 --qos=debug")

# Standard CPU
sbatch_cpu   = SbatchArrayJobstarter(max_cores=200, options="--time=24:00:00 --mem=8G")

# GPU
sbatch_gpu   = SbatchArrayJobstarter(max_cores=20, gpus=1,
                                       options="--time=08:00:00 --partition=gpu --mem=32G")

# Long-running MD
sbatch_md    = SbatchArrayJobstarter(max_cores=8, options="--time=72:00:00 --partition=long")
```

## When the runner appears to "hang"

`squeue -n <jobname>` is poll-only — if the cluster's scheduler is slow or
the queue is deep, the runner blocks here. Diagnose:

```bash
squeue -u $USER -o "%i %j %T %M %R"
sacct -X --name <jobname> --format=JobID,State,Elapsed,ExitCode
```

If tasks are PENDING with `Resources` or `Priority` as the reason, the
cluster is doing its thing; the runner will return when they drain.

If tasks are RUNNING but the output dir has been empty for hours, attach to
a compute node (`ssh <node>; ps -fu $USER`) to see what each task is doing.

## When a task fails silently

The runner only raises if `collect_scores()` then can't find enough
outputs to merge. A task can crash before producing any files; in that
case:

1. Check `<work_dir>/<prefix>/<jobname>_*_slurm.err` for stack traces.
2. Check the per-pose subtree under `<work_dir>/<prefix>/output_pdbs/`
   (or the tool's analogue) to see which descriptions are missing.
3. If `fail_on_missing_output_poses=True` was set, the runner will
   refuse to return; otherwise it silently keeps whatever did succeed.

Set `fail_on_missing_output_poses=True` on RFdiffusion / Rosetta when you
need strict guarantees that every input got an output.

## Filesystem caveats

- Many clusters' shared scratch is NFS; some tools (e.g. RFdiffusion) race
  on directory creation when many tasks start at once. ProtFlow inserts a
  small random `sleep` (0–5 s) in RFdiffusion commands to stagger them.
  If you see "FileExistsError" or "stale NFS handle" still, increase the
  range or move work_dir to a more local FS.
- `pickle` storage format is fastest on read/write but is *not* portable
  across pandas versions. For long-running campaigns or cross-cluster
  sharing, prefer `json` or `parquet`.
- ResidueSelection objects do not round-trip through `csv` cleanly unless
  you explicitly populate the `import_resselection_cols` column. Use `json`
  or `pickle` for any campaign that uses motif tracking.
