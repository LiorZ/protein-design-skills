# Multi-GPU and Multi-Node Sharding

Genie 3 has two orthogonal scaling axes:

1. **Per-process multi-GPU** — `--num-devices N` runs N GPUs on one node via PyTorch Lightning's DDP.
2. **Multi-node sharding** — `--shard-id ID --num-shards N` slices the workload (samples or beam-search runs) across N independent processes (typically one per node).

The two compose: `--num-devices 4 --shard-id 0 --num-shards 8` → node 0 of 8, using 4 GPUs.

## Single-node multi-GPU

```bash
genie3 run -c <CFG> --num-devices 4
```

Effects:
- Overrides `runtime.num_devices` in the config.
- Generation: PyTorch Lightning DDP across 4 GPUs.
- Evaluation: workers are sharded across the 4 devices; one log subdirectory per worker under `logs/runs/<run>/workers/`.

The `genie3 run` parent process spawns three child processes sequentially (`generate`, `evaluate`, `evaluate --reduce`); each child re-initializes the distributed process group, so GPU memory is fully released between stages.

## Multi-node — generation

One process per node, each handling a slice of `dataset.n_sample`:

```bash
# On node k of N (k = 0, 1, ..., N-1):
genie3 generate -c <CFG> --num-devices <PER_NODE> --shard-id k --num-shards N
```

Slicing semantics (in `_apply_shard_to_config`):

- **Non-beam**:
  ```
  samples_per_shard = ceil(n_sample / num_shards)
  shard's slice = [shard_id * samples_per_shard, shard_id * samples_per_shard + samples_per_shard)
  dataset.sample_index_offset = shard_id * samples_per_shard  # global IDs
  ```
- **Beam search**:
  ```
  outputs_per_run = beam_width if n_output <= 0 else n_output
  total_runs = ceil(n_sample / outputs_per_run)
  runs_per_shard = ceil(total_runs / num_shards)
  search.requested_n_sample = n_sample (preserved globally for trimming)
  ```

Output landing pattern:
- Generated PDBs: `<rootdir>/<problem>/pdbs/sample_<global_id>.pdb`
- Shard markers: `<rootdir>/<problem>/.shard_markers/generate.<shard_id>.done`

Sample IDs are globally unique because of `sample_index_offset`, so concatenated CSVs are safe.

## Multi-node — evaluation

Same flag pattern; each shard evaluates its slice of the generated PDBs.

```bash
genie3 evaluate -c <CFG> --num-devices <PER_NODE> --shard-id k --num-shards N
```

After all eval shards finish, **run the reduce step exactly once on a single node**:

```bash
genie3 evaluate --reduce -c <CFG>
```

Reduce:
- Scans all `evaluate.<id>.done` markers under `<problem>/.shard_markers/`.
- Concatenates per-shard CSVs.
- Runs the application-specific reducer (`UnconditionalReducer` / `ScaffoldReducer` / `BinderReducer`) — applies success filters, runs FoldSeek clustering.
- Writes final CSVs and `<problem>/results/eval.done` sentinel.

## Status and recovery

```bash
genie3 status -c <CFG>
```

Outputs per-problem progress and **prints exact re-run commands for missing shards**:

```
🟡 Generation  01_bhrf1  6/8 shards  ✅✅⬜✅✅⬜✅✅

   Re-run missing shards:
   genie3 generate -c <CFG> --shard-id 2 --num-shards 8
   genie3 generate -c <CFG> --shard-id 5 --num-shards 8
```

Re-running a missing shard is idempotent — completed shards' marker files are not overwritten.

## Recommended cluster recipes

### Slurm — same job array for all shards

```bash
#!/bin/bash
#SBATCH --job-name=genie3-binder
#SBATCH --array=0-7
#SBATCH --gres=gpu:4
#SBATCH --time=12:00:00

source ~/.bashrc
conda activate genie3
cd /path/to/genie3

genie3 generate -c configs/binder.yaml \
    --num-devices 4 \
    --shard-id $SLURM_ARRAY_TASK_ID \
    --num-shards 8
```

Then a follow-up array for evaluation:

```bash
#SBATCH --array=0-7
genie3 evaluate -c configs/binder.yaml \
    --num-devices 4 \
    --shard-id $SLURM_ARRAY_TASK_ID \
    --num-shards 8
```

Then a single reduce job:

```bash
genie3 evaluate --reduce -c configs/binder.yaml
```

### NERSC / MPI environments

`genie3 train` supports `--mpi-plugin` for distributed training. `generate`/`evaluate` use plain DDP and don't require MPI; they read `LOCAL_RANK`/`RANK` from the environment for distributed-aware logging.

## Environment variables that leak between processes

`genie3 run` sets these in the child environment:

| Var | Purpose |
|-----|---------|
| `GENIE3_RUN_DIR` | Run-log directory, so child uses the same one |
| `GENIE3_RUN_LOG` | Path to the parent's master log file |
| `GENIE3_WORKERS_DIR` | Sub-dir for per-worker log files |
| `GENIE3_PARENT_COMMAND` | Always `run` — used by `_is_child_run_stage()` to suppress redundant headers |
| `GENIE3_VERBOSE` | `1` if `--verbose` was passed to the parent |

When sharding manually (no `genie3 run` parent), you don't need any of these.

## Performance tips

- Use one process per node; let DDP handle intra-node parallelism. Avoid running multiple `genie3 generate` processes on the same node — they will fight for GPUs.
- Prefer many small shards over few large ones if your job scheduler has short max walltime. With `n_sample=200, num_shards=20`, each shard handles 10 samples and finishes in ~1 hr.
- The reduce step is single-node and CPU-light; run it on a CPU-only login node.
- Beam search compounds compute cost (per-checkpoint ColabFold). Budget ≥4 GPUs per node for beam runs.
