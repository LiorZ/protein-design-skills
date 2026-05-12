# Batch inference

`chai-lab fold-batch` runs the model on **every `.fasta` / `.fa` file in
a directory**, sharding work across GPUs. This is the right primitive
for design campaigns: feed a directory of one-fasta-per-design and let
the worker pool drain it.

## CLI

```bash
chai-lab fold-batch designs_dir/ \
                    --output-dir results_dir/ \
                    --devices 0,1,2,3
```

All `fold` flags are passed through (MSAs, restraints, templates,
sample counts, seed, etc.). The flag is `--devices` with a
comma-separated list of GPU indices; omit it to use all visible CUDA
devices.

Output layout (one directory per input FASTA, stem-named):

```
results_dir/
  design_001/
    pred.model_idx_0.cif … pred.model_idx_4.cif
    scores.model_idx_0.npz … scores.model_idx_4.npz
  design_002/
    …
```

If a FASTA fails (invalid input, OOM, etc.) the worker logs the error
and moves on; other workers keep running. The CLI returns the full
list of `BatchResult` records — successful and failed.

## Python entrypoint

```python
from pathlib import Path
from chai_lab.batch import run_batch_inference

results = run_batch_inference(
    input_dir=Path("designs/"),
    output_dir=Path("results/"),
    devices="0,1,2,3",        # or None for all GPUs
    use_msa_server=False,
    constraint_path=None,
    num_diffn_samples=5,
    num_trunk_recycles=3,
    seed=0,
    low_memory=True,
)

print(sum(r.success for r in results), "ok /", len(results), "total")
for r in results:
    if not r.success:
        print(r.fasta_file.name, "failed:", r.error_message)
```

Each `BatchResult` has `fasta_file`, `output_dir`, `success`, and
optionally `error_message`.

## How parallelism works

- One **worker process per GPU**, started with the `spawn` start method
  (CUDA-safe).
- All workers share a `multiprocessing.Queue` of `(fasta, sub_output)`
  tuples.
- Each worker calls `chai_lab.chai1.run_inference` with its own GPU,
  one FASTA at a time.
- Model weights and ESM weights load **per worker** at startup
  (~10–30 s of warm-up), then stay resident for the rest of the batch.
- The cache `_component_cache` inside `chai1.py` keeps each TorchScript
  module on the worker GPU between fastas — much faster than reloading.

There is **no within-fold model parallelism** — Chai uses one GPU per
prediction.

## Practical tips for campaigns

- **Use single-sequence mode (`use_msa_server=False`) for designed
  proteins**: there is no MSA signal and you'll spam the public server.
- **Pre-generate MSAs** to a local directory if your designs share a
  target: pass `msa_directory=Path("./shared_msas/")` (the lookup is by
  sequence hash, so per-design MSAs are still per-design).
- **Use `low_memory=True` (default) on 24–48 GB GPUs**, especially when
  your designs vary in length. Some sizes will trigger crop-size 1024
  or 1536 which needs more VRAM.
- **Cap `num_diffn_samples`** at 2 or 3 during early-stage screening to
  speed up; bump to 5 for the final round.
- **Use `--fasta-names-as-cif-chains`** if you want consistent chain
  labels across thousands of designs (e.g. always `T` for target, `B`
  for binder). The names must be single-character, valid PDB chain IDs.
- **Set `--seed`** for reproducibility across the entire batch. Each
  fasta uses the same seed, so re-running gives identical structures.

## Typical sizing

| GPUs | Design length | Throughput |
|------|---------------|------------|
| 1× A100 80GB | ~150 AA binder + 250 AA target, 5 samples, no MSA | ~30–60 s per design |
| 4× A100 | same | ~50–200 designs / hour |
| 1× RTX 4090 | same | ~2–3× slower than A100 |

(MSAs at fold time add the MSA-search round-trip — slow if going via
the public ColabFold server.)

## Failure modes

- **One worker dies and stops draining the queue.** The other workers
  keep going. After the run, check `error_message` for the FASTAs whose
  workers died (CUDA OOM, model crash, etc.). Re-run those failures
  with a smaller batch or more VRAM.
- **All workers stall waiting for ColabFold.** The public MMseqs2
  server is rate-limited. Host your own, or precompute MSAs.
- **OOM on long inputs.** Cap `num_diffn_samples=1`, keep
  `low_memory=True`, and consider sorting your input directory by
  length so failures cluster.
