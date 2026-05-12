# Running on SLURM (multi-job parallelism)

BoltzGen's recommended parallel-campaign pattern is a **SLURM job array
of single-GPU `boltzgen run` tasks**, followed by `boltzgen merge` and a
filtering refresh on a login node.

Each array task generates a slice of the total design budget end-to-end
(design → IF → folding → analysis → filtering). The per-task filtering
output is overwritten by the final merge-and-refilter on the login node.

## Why job arrays rather than `--devices 8`

You *can* parallelize within a step (`--devices 8`), but:

- An 8-GPU single-step run still serializes the steps (design, then IF,
  then folding) — no overlap.
- Job arrays trivially share the queue's idle GPUs across users.
- Failure isolation is per-task: lost GPU = lost 1k designs, not 60k.
- Length-range sampling is per-batch, so launching many independent
  tasks naturally diversifies sampled lengths.

If you have a single fat node with N GPUs and want minimum latency on a
small campaign (say, 1k designs), `--devices N` is fine.

## The bundled example

`slurm-example/` in the repo has two files:

- `run_job_array.slurm` — the per-task SLURM script.
- `run.sh` — the orchestrator with `submit` and `process` modes.

### `run_job_array.slurm`

```bash
#!/bin/bash
#SBATCH -C gpu
#SBATCH -q regular
#SBATCH -t 03:00:00
#SBATCH -N 1
#SBATCH --gpus-per-node=1
#SBATCH --array=1-2                # overridden by run.sh
#SBATCH --mem=64G
#SBATCH -J boltzgen

set -euo pipefail

design_spec="$1"
outdir="$2"
num_designs="$3"
conda_environment="$4"
shift 4
extra_args=("$@")

module load conda
conda activate "$conda_environment"

job_outdir="${outdir}/task-${SLURM_ARRAY_JOB_ID}-${SLURM_ARRAY_TASK_ID}"
mkdir -p "${job_outdir}"

srun --ntasks=1 --gpus-per-task=1 \
  boltzgen run "$design_spec" \
    --output "${job_outdir}" \
    --num_designs "$num_designs" \
    "${extra_args[@]}"
```

### `run.sh`

```bash
#!/bin/bash
set -e

DESIGN_SPEC=/path/to/design/spec.yaml
MERGED_OUT=/path/to/your/output/directory
NUM_TASKS=20
NUM_DESIGNS_PER_TASK=1000
CONDA_ENVIRONMENT=/path/to/conda/environment/with/boltzgen
CACHE_DIR=/path/where/models/are/saved
ACCOUNT=YOUR_ACCOUNT
TIME=05:00:00

OUT="${MERGED_OUT}/task-outputs"
LOGS="${MERGED_OUT}/task-logs"

case "$1" in
  submit)
    mkdir -p "$OUT" "$LOGS"
    sbatch -A "$ACCOUNT" -t "$TIME" --export=ALL \
           --array=1-$NUM_TASKS \
           -o "$LOGS/stdout.%A-%a.log" -e "$LOGS/stderr.%A-%a.log" \
           run_job_array.slurm \
           "$DESIGN_SPEC" "$OUT" "$NUM_DESIGNS_PER_TASK" \
           "$CONDA_ENVIRONMENT" \
           --protocol protein-anything --cache "$CACHE_DIR"
    squeue --me
    ;;
  process)
    boltzgen merge "$OUT"/task-* --output "$MERGED_OUT"
    boltzgen run "$DESIGN_SPEC" --steps filtering \
      --protocol protein-anything --output "$MERGED_OUT"
    ;;
  *)
    echo "Usage: $0 {submit|process}" >&2
    exit 1
    ;;
esac
```

Workflow:

```bash
$ bash run.sh submit    # submit the array
# ... wait for all tasks to finish ...
$ bash run.sh process   # merge + filter on the login node
```

## Sizing the array

For a target campaign size of `T = 60,000` designs across `N` tasks:

| Per-task `--num_designs` | Per-task wall time (A100) | Notes                                                          |
|--------------------------|---------------------------|----------------------------------------------------------------|
| 100                      | ~10 min                   | Tiny tasks, big array. Good for queues with short max walltime. |
| 1000                     | ~1.5 h                    | Sweet spot; the slurm-example default.                          |
| 5000                     | ~7 h                      | Risk of hitting walltime; need `--reuse` if so.                 |

`--num_designs T/N` rounded up.

## Surviving partial failures with `--reuse`

If a task gets killed (preemption, timeout, OOM), launch the same task
again pointing at the same output dir with `--reuse`. The pipeline picks
up where it left off — already-generated CIFs are not redone.

```bash
sbatch ... run_job_array.slurm "$DESIGN_SPEC" "$OUT" 1000 "$CONDA" \
  --protocol protein-anything --reuse
```

## Merging outputs

`boltzgen merge` stitches finished output dirs into one. It:

1. Copies CIFs from each source's `intermediate_designs/`,
   `intermediate_designs_inverse_folded/`, `refold_cif/`,
   `refold_design_cif/`.
2. Renames any colliding design IDs (so all are unique in the merged
   dir).
3. Concatenates `aggregate_metrics_analyze.csv` and re-emits
   `per_target_metrics_analyze.csv`.
4. Writes new merged `config/` files inferred from the first source.

```bash
boltzgen merge \
  task-outputs/task-1234-1 \
  task-outputs/task-1234-2 \
  task-outputs/task-1234-3 \
  --output merged_run

# Then refilter on the combined set
boltzgen run spec.yaml --steps filtering --output merged_run \
  --protocol protein-anything --budget 60 --alpha 0.05
```

The `--overwrite` flag exists for backwards-compat and is now always-on.

## Cache strategy on shared filesystems

The 6 GB of weights and the moldir should sit in a shared cache so all
tasks read from one location:

```bash
CACHE_DIR=/scratch/$USER/bg_cache
boltzgen download all --cache "$CACHE_DIR"   # one-time

# every task
boltzgen run … --cache "$CACHE_DIR"
# or via env
export HF_HOME="$CACHE_DIR"
```

Avoid putting the cache on `$HOME` on most HPC sites — quota / latency.

## Within-task multi-GPU

If a single node has 4 GPUs and you want to use all of them for one task
(e.g. on a single shared node, not in an array), set `--devices 4`:

```bash
boltzgen run spec.yaml --output OUT \
  --num_designs 4000 \
  --devices 4 --num_workers 4
```

This uses PyTorch-Lightning DDP within each step. Per-step config
overrides also accept `trainer.devices=4` if you want different device
counts per step:

```bash
boltzgen run spec.yaml --output OUT \
  --config design trainer.devices=4 \
  --config folding trainer.devices=2 \
  --config analysis num_processes=32
```

## Anti-pattern: `--no_subprocess` with multiple devices

`--no_subprocess` keeps every step in the main process. It is **only**
useful for single-GPU debugging — multi-GPU within a step requires
subprocess execution. The default is correct; only flip it if you know
why.

## Anti-pattern: launching arrays from the login node without `--cache`

By default models go to `~/.cache`. On most HPC sites `$HOME` is
quota-limited and slow. **Always** set `--cache` (or `HF_HOME`) to a
scratch / project path explicitly.
