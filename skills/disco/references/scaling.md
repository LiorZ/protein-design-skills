# Scaling DISCO — multi-GPU, multi-node, large screens

DISCO uses [Lightning Fabric](https://lightning.ai/docs/fabric/stable/)
with `DDPStrategy(find_unused_parameters=False)` for distributed
inference. Sample-level parallelism is the easy axis: each
`(job, seed)` pair is independent, so DDP shards the dataloader across
ranks and you get near-linear speedup.

## Single GPU

The default. Nothing to configure beyond `CUDA_VISIBLE_DEVICES`:

```bash
CUDA_VISIBLE_DEVICES=0 python runner/inference.py \
  experiment=designable effort=max \
  input_json_path=input_jsons/heme_b.json \
  seeds=\[0,1,2,3,4\]
```

## Single node, multiple GPUs

Launch through `torchrun`. The runner picks up the rank from `RANK` /
`LOCAL_RANK` env vars:

```bash
torchrun --nproc_per_node=4 runner/inference.py \
  experiment=designable effort=max \
  input_json_path=input_jsons/heme_b.json \
  seeds=\[0,1,2,3,4,5,6,7\]
```

Total samples = `len(seeds) × len(jobs)`. With 4 GPUs and 8 seeds × 3
jobs = 24 samples, each GPU processes 6.

Alternatively, set `fabric.devices` if you'd rather control through
Hydra (Lightning Fabric reads it):

```bash
torchrun --nproc_per_node=4 runner/inference.py \
  fabric.devices=4 \
  experiment=designable effort=max \
  input_json_path=input_jsons/heme_b.json \
  seeds=\[0,1,2,3,4,5,6,7\]
```

## Multi-node (SLURM)

Set `fabric.num_nodes` and use `srun`. Each node runs
`--nproc_per_node` worker processes:

```bash
#!/bin/bash
#SBATCH --nodes=4
#SBATCH --gpus-per-node=8
#SBATCH --tasks-per-node=8

srun python runner/inference.py \
  fabric.num_nodes=4 \
  experiment=diverse effort=max \
  input_json_path=input_jsons/all_priorities_ligands_split_0.json \
  seeds=\[$(seq -s "," 0 49)\]
```

Lightning Fabric handles process group setup automatically from SLURM
env vars (`SLURM_JOB_NODELIST`, `SLURM_NODEID`, etc.). Verify by
checking the first log line, which prints `Fabric: ..., rank: X,
world_size: Y`.

## Sharding strategy

The dataloader is constructed by `get_inference_dataloader`. With
distributed training, the dataset is sharded across ranks via Lightning's
distributed sampler. **Run-resume is per-sample**, so even if a rank
crashes mid-run, only the unfinished samples are re-attempted next time.

Implications:

- **Add seeds**, don't shrink them, for a re-run: shrinking seeds will
  cause some ranks to be idle for the rest of the run.
- **Splitting jobs across separate JSON files** is a perfectly good
  alternative to one big JSON for multi-node — the four
  `all_priorities_ligands_split_*.json` files use exactly this pattern.

## Practical scaling tips

1. **Bottleneck is forward-pass time, not dataloader.** Increase GPU
   count for linear speedup until you hit per-rank batch=1 limits
   (DISCO's `infer_batch_size=1` is the only tested setting).
2. **`effort=fast` is ~4× faster than `effort=max`**. For unconditional
   prototyping you can do 4× more seeds at the same cost. (Don't use
   `fast` for conditional generation.)
3. **`sample_diffusion.noisy_guidance.enabled=false`** roughly halves
   wall-clock time per sample by avoiding the guidance forward pass.
   Trade-off: ~10% co-designability drop with `designable` preset.
4. **First-launch JIT compile** runs once per rank — multi-node startup
   can take 5–10 minutes before any sample is produced. Once compiled,
   the caches persist across runs.
5. **CUTLASS kernel cache is per-machine**. On a fresh node, expect the
   JIT compile penalty again. SLURM allocations with new nodes will
   re-compile.

## Cost estimation

A rough rule of thumb (paper numbers, A100 80GB):

| Setting | Length 200 | Length 300 |
|---------|-----------:|-----------:|
| `effort=fast, designable` | ~30 s / sample | ~60 s / sample |
| `effort=fast, diverse` | ~25 s / sample | ~50 s / sample |
| `effort=max, designable` | ~90 s / sample | ~180 s / sample |
| `effort=max, diverse` | ~60 s / sample | ~120 s / sample |

Use these to estimate run time *very* roughly. Heavy ligands (>50
atoms) inflate these numbers.

For a Studio-179 split (44–45 ligands × 3 lengths × 5 seeds × ~90 s) ≈
**~17–18 GPU-hours per split** on an A100. A 32× A100 node-hour
allocation runs the full benchmark.

## Monitoring

DISCO logs to stdout (one line per sample success / failure). There's
no built-in W&B / TensorBoard logger in the inference path (training
has them, inference does not). The `configs/logger/many_loggers.yaml`
default loads multiple Lightning loggers but they're empty for
inference.

To monitor progress:

```bash
# count completed samples
ls output/pdbs/*.pdb | wc -l

# tail the log if you redirected stdout
tail -f run.log

# watch the err dir for failures
watch -n 5 ls output/ERR/
```

## Multi-rank failures

If one rank dies mid-run:

- Lightning DDP defaults will tear down the whole job.
- **Re-launch the same command.** Run-resume keeps completed samples
  and the unfinished ones get retried.
- Check `output/ERR/<name>.txt` for per-sample tracebacks.

For very long runs, wrap the launch in a retry loop:

```bash
for i in 1 2 3; do
  srun python runner/inference.py ... && break
  echo "Retry $i ..."
done
```

## Large screens (hundreds of ligands)

For Studio-179-scale screens, the rough recipe is:

1. Split the JSON into ~4–8 files, each ~25–50 ligands.
2. Submit each split as a separate SLURM job with N nodes.
3. Use the same `dump_dir` across all jobs (resume-safe).
4. Once all jobs complete, run your refold + filter pipeline.

Each split has its own `_ligands.txt`, `pdbs/`, `sequences/`, and `ERR/`
namespaces because the `name` field is unique per job. There's no
cross-job interference as long as job names are distinct across splits.
