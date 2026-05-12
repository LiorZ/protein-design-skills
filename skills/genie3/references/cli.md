# CLI Reference

The `genie3` console script is registered by `setup.py` and dispatches to
`genie3.cli:main`. It has five subcommands: `run`, `generate`, `evaluate`,
`status`, `train`.

## Top-level usage

```bash
genie3 <subcommand> [-c CONFIG] [--num-devices N] [--shard-id ID] [--num-shards N]
                    [--verbose] [--log-dir DIR] [--reduce]
```

A run always writes a structured log directory under `--log-dir` (default `logs/runs`). The terminal shows a compact progress line; pass `--verbose` for full live output.

## Subcommands

### `genie3 run`

Generate → evaluate → reduce, in that order, in **three sequential child processes** (so each stage starts with a fresh CUDA context and freed GPU memory). For configs with a `rounds:` block, runs each round sequentially and resumes from `.generate_done` / `.evaluate_done` sentinel files.

```bash
genie3 run -c <CONFIG> [--num-devices N] [--verbose] [--log-dir DIR]
```

Flags:
- `-c, --config PATH` — required experiment YAML
- `--num-devices N` — overrides `runtime.num_devices`
- `--verbose` — stream child stdout/stderr to terminal
- `--log-dir DIR` — root for run logs (default `logs/runs`)

Behavior:
- Sets env vars `GENIE3_RUN_DIR`, `GENIE3_RUN_LOG`, `GENIE3_WORKERS_DIR`, `GENIE3_PARENT_COMMAND=run`, `GENIE3_VERBOSE` for the children so they log into the same run directory.
- Calls `_cleanup_generation_runtime()` between `generate` and `evaluate` (gc, `torch.cuda.empty_cache`, destroys distributed process group if init'd).
- Iterative mode: writes a temp YAML per round into `tempfile.NamedTemporaryFile(suffix='.yaml')`, with `paths.rootdir` set to `<rootdir>/<round_id>` and `cond_strategy` injected into `generation.dataset`.

### `genie3 generate`

Run *only* the generation stage on a single shard.

```bash
genie3 generate -c <CONFIG> [--num-devices N] [--shard-id ID] [--num-shards N]
                            [--verbose] [--log-dir DIR]
```

Flags:
- `--shard-id ID` — zero-based shard index, must be in `[0, num_shards)`
- `--num-shards N` — total shards (default 1)

Behavior:
- Loads config, resolves shard slice via `_apply_shard_to_config`:
  - **Non-beam**: splits `dataset.n_sample` evenly across shards, sets `dataset.sample_index_offset` to the shard's starting global index.
  - **Beam**: splits the *number of beam-search runs* (= `ceil(n_sample / outputs_per_run)`) across shards, preserving global `requested_n_sample` so `beam.py` trims the final run correctly.
- Writes shard markers under `<rootdir>/.shard_markers/generate.<shard_id>.done` (or `<problem>/.shard_markers/...`).

### `genie3 evaluate`

Run evaluation for one shard, or merge all shard outputs.

```bash
# One shard (per node):
genie3 evaluate -c <CONFIG> --shard-id ID --num-shards N [--num-devices N]

# Reduce — run ONCE after all shards:
genie3 evaluate --reduce -c <CONFIG>
```

Behavior:
- Per-shard: loads generated PDBs from `<rootdir>/[<problem>/]pdbs/`, applies inverse folding (default ProteinMPNN, `num_seq=8`), then folds (default ColabFold `mode=template`, `num_models=5`, `num_recycles=20`).
- `--reduce`: scans `.shard_markers/evaluate.*.done` markers, concatenates per-shard CSVs, runs the per-application reducer (`UnconditionalReducer` / `ScaffoldReducer` / `BinderReducer`), and writes `info.csv`, `successful_*`, FoldSeek clusters into `<rootdir>/[<problem>/]results/`. Touches `<problem>/results/eval.done` when complete.
- Reduce is unsharded — pass shard-id 0 num-shards 1.

### `genie3 status`

Print a per-problem (or per-round) progress table.

```bash
genie3 status -c <CONFIG>
```

Output sample for sharded binder run:

```
📁 examples/binder_design/output

✅ Generation  01_bhrf1   8/8 shards  ✅✅✅✅✅✅✅✅
🟡 Evaluation  01_bhrf1   5/8 shards  ✅✅✅⬜✅⬜✅⬜

   Re-run missing shards:
   genie3 evaluate -c <CFG> --shard-id 3 --num-shards 8
   genie3 evaluate -c <CFG> --shard-id 5 --num-shards 8
   genie3 evaluate -c <CFG> --shard-id 7 --num-shards 8
```

For iterative mode, prints one line per round with `[cond_strategy]` and per-round generate/evaluate ticks.

### `genie3 train`

Launch model training (PyTorch Lightning).

```bash
genie3 train --config <CONFIG> --devices N [--num-nodes M]
             [--test] [--mpi-plugin] [--memory-snapshot] [--reset-dataloader-state]
```

Flags:
- `--config PATH` — training config YAML
- `-d, --devices N` — GPUs per node (required)
- `-n, --num-nodes M` — total nodes (default 1)
- `-t, --test` — disable W&B remote logging (use for local smoke tests)
- `--mpi-plugin` — use the MPI environment plugin for distributed setup
- `--memory-snapshot` — enable CUDA memory snapshot collection
- `--reset-dataloader-state` — clear dataloader checkpoint state before training

See [training.md](training.md) for training config schema.

## Shared flag reference

| Flag | Default | Description |
|------|---------|-------------|
| `-c / --config PATH` | (required) | Path to experiment YAML |
| `--num-devices N` | from `runtime.num_devices` (default 1) | GPUs per process |
| `--verbose` | off | Stream live runtime output |
| `--log-dir PATH` | `logs/runs` | Root directory for structured logs |
| `--shard-id ID` | 0 | Zero-based shard index for this node |
| `--num-shards N` | 1 | Total shards across all nodes |
| `--reduce` (evaluate only) | off | Run reduce step instead of a shard |

Flag validation:
- `num_shards >= 1`, else exit 2
- `0 <= shard_id < num_shards`, else exit 2

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Run failed (exception) — check `<log-dir>/.../*.log` |
| `2` | CLI argument validation error |
| `130` | Interrupted (Ctrl-C) |

## Process model — what happens when you call `genie3 run`

```
genie3 run -c CFG --num-devices 4
   │
   ├─ creates run dir under logs/runs/<timestamp>-<command>/
   ├─ loads config, decides single-shot vs iterative
   │
   └─ for single-shot:
        ├── subprocess: genie3 generate -c CFG --num-devices 4
        ├── _cleanup_generation_runtime()  (gc + cuda cache + destroy PG)
        ├── subprocess: genie3 evaluate -c CFG --num-devices 4
        └── subprocess: genie3 evaluate -c CFG --num-devices 4 --reduce
```

This three-process pattern is intentional. The `evaluate` stage often loads ESMFold/ColabFold weights that compete with generation for VRAM; using fresh subprocesses guarantees clean state.

## Distributed launch detection

`_is_primary_process()` returns true if `LOCAL_RANK==0` (or `RANK==0`, or neither set). Failure / interrupt messages are only printed on the primary process to keep multi-rank logs clean.

## Re-running and resumability

- **Single-shot**: re-running `genie3 run` does not skip stages by itself, but each shard within a stage is idempotent — completed shards (with marker files in `.shard_markers/`) are skipped and only missing shards re-run.
- **Iterative**: `_run_iterative` checks `.generate_done` / `.evaluate_done` per round and skips completed rounds entirely.
- **Reduce**: writes `<rootdir>/<problem>/results/eval.done`. To force re-reduce, delete that sentinel.

Use `genie3 status -c <CFG>` to see exactly what is missing and the suggested re-run commands.
