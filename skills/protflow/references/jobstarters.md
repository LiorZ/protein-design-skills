# JobStarters — Local vs SLURM

A JobStarter is the submission backend. ProtFlow ships two concrete
implementations and an abstract base class.

## `LocalJobStarter`

```python
from protflow.jobstarters import LocalJobStarter

js = LocalJobStarter(max_cores=4)
```

What it does:

- Spawns commands as concurrent `subprocess.Popen` children, bounded by
  `max_cores`.
- Streams stdout/stderr to per-process log files under the runner's
  `output_path` (`process_<i>.out` / `process_<i>.err`).
- Raises `ProcessError` if any subprocess exits non-zero (after the
  base-class wrapper catches and re-raises with stderr context).
- `wait_for_job` is a no-op: `start()` already blocks.

Use for: laptop / single workstation runs, smoke tests, single-GPU dev boxes.

## `SbatchArrayJobstarter`

```python
from protflow.jobstarters import SbatchArrayJobstarter

js = SbatchArrayJobstarter(
    max_cores=50,           # concurrent array tasks
    gpus=1,                 # → '--gpus-per-node 1' added to sbatch
    options="--time=08:00:00 --partition=gpu --mem=32G",  # appended verbatim
    remove_cmdfile=False,   # keep the _cmds file for debugging
    batch_cmds=None,        # group commands into N composite tasks (joined by ;)
)
```

How it works:

1. Writes one line per command to `<work_dir>/<jobname>_cmds`.
2. Submits `sbatch -a 1-N%max_cores -J <jobname> <options> --wrap '...sed -n
   ${SLURM_ARRAY_TASK_ID}p <cmdfile> | eval...'`.
3. If `wait=True` (default), polls `squeue -n <jobname>` every 5 s until
   empty, then sleeps 5 s more (small buffer for filesystem propagation).
4. After completion, captures the last 16 KiB of `<jobname>_slurm.err` into
   `self.last_error_message` so the base Runner wrapper can attach it to any
   exception.

### Array-job sizing

If `len(cmds) > self.slurm_max_arrayjobs` (default `1000`), the cmd list is
auto-split and `start()` recurses. Most SLURM installs cap arrays at 1000 or
10000 — adjust `js.slurm_max_arrayjobs` to match your cluster's
`MaxArraySize`.

### `batch_cmds`

When you have thousands of fast commands, the per-task SLURM overhead
dominates. Pass `batch_cmds=N` to merge them into `N` `;`-joined composite
tasks (still one array). Cuts the array to N tasks; each task runs many
sequential commands.

### `options=` is appended verbatim

You can pass a string or a list:

```python
SbatchArrayJobstarter(options="--time=08:00:00 --qos=high --partition=gpu")
SbatchArrayJobstarter(options=["--time=08:00:00", "--qos=high"])
```

Both work. Don't include `--job-name` or `--array` (ProtFlow sets those).

### Capture log layout

For every `.start(...)` call, ProtFlow writes:

```
<output_path>/<jobname>_<ts>_cmds              # the array cmd file
<output_path>/<jobname>_<ts>_slurm.out         # combined stdout (--open-mode=append)
<output_path>/<jobname>_<ts>_slurm.err         # combined stderr
<output_path>/<jobname>_<ts>_jobstarter.log    # sbatch invocation output
```

`<ts>` is a microsecond timestamp suffix appended by `add_timestamp()` to
prevent collisions when re-running the same prefix.

When a runner crashes, the **last 16 KiB of `<jobname>_<ts>_slurm.err`** is
appended to the Python exception by `Runner._wrap_run_with_stderr_context`.
Read that first.

## Resolution priority

A runner picks its jobstarter using this order:

```
1. runner.run(jobstarter=...)              # per-call override
2. Runner(jobstarter=...)                  # per-runner default
3. poses.default_jobstarter                # campaign default
```

The first non-`None` wins. If all three are `None`, the runner raises
`ValueError("No Jobstarter was set ...")`.

This is exactly the right shape for: a campaign that's mostly GPU sbatch, but
one step (e.g. Rosetta relax) wants the CPU partition — just pass
`jobstarter=slurm_cpu` to that one `.run()` call.

## SLURM accounting helper

```python
from protflow.jobstarters import get_SLURM_stats

stats = get_SLURM_stats(
    job_name=my_runner.current_jobstarter.last_job_name,
    start_time="2026-05-12T09:00:00",
)
# {'total_cpu_sec': ..., 'avg_task_runtime_sec': ..., 'state': 'COMPLETED', ...}
```

Notes:

- Must be called on a node where `sacct` is available (typically the login
  node).
- Pass `start_time` to avoid matching stale jobs with the same name from
  earlier sessions.
- Returns `{"error": "..."}` on failure (does not raise).
- State is `"COMPLETED"` only if **every** task is `COMPLETED`. Otherwise
  `"MIXED (<states>)"`.

There's also `SbatchArrayRunnerTimer` (a context-manager) that records
`session_start` and pairs naturally with `get_SLURM_stats` — see the
docstring in `protflow.jobstarters`.

## Writing a custom JobStarter

Subclass `JobStarter` and implement two methods:

```python
class MyStarter(JobStarter):
    def start(self, cmds, jobname, wait, output_path):
        # submit, optionally block on wait
        ...

    def wait_for_job(self, jobname, interval):
        # poll until done
        ...
```

`Runner.generic_run_setup` will accept any `JobStarter` subclass. Useful for
PBS / LSF / Kubernetes / cloud-batch backends.
