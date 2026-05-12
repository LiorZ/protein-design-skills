# Training

`genie3 train` launches model training using PyTorch Lightning. This page covers
the CLI, the training data layout, and config conventions. Most users will
*never* train — the released `pretrained/v1/checkpoints/step=600000.ckpt`
is what every inference workflow loads by default.

## CLI

```bash
genie3 train \
    --config <CONFIG> \
    --devices N \
    [--num-nodes M] \
    [--test] \
    [--mpi-plugin] \
    [--memory-snapshot] \
    [--reset-dataloader-state]
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--config <PATH>` | yes | — | Training configuration YAML |
| `-d, --devices N` | yes | — | Number of GPUs per node |
| `-n, --num-nodes M` | no | `1` | Number of compute nodes |
| `-t, --test` | no | off | Disable W&B remote logging (use for local smoke tests) |
| `--mpi-plugin` | no | off | Use the MPI Lightning environment plugin |
| `--memory-snapshot` | no | off | Enable CUDA memory snapshot collection (debug) |
| `--reset-dataloader-state` | no | off | Clear dataloader checkpoint state before training |

Training does not use the unified experiment YAML schema — it uses a separate
training-specific config. Look in the upstream Genie 3 repo for example
training configs (typically under a `configs/training/` directory if shipped).

## Training data

Downloaded by:

```bash
bash scripts/setup/download.sh --data
```

| Dataset | Manifest | Size | Notes |
|---------|----------|------|-------|
| AlphaFold DB representatives, L≤512, pLDDT≥70 | `data/train/afdbreps_l-512_plddt-70/info.csv` | many GB | Filtered AFDB clusters; primary unconditional pretraining set |
| PiNDER (2024-02) | `data/train/pinder/2024-02/info.csv` | many GB | Protein interaction set used for binder-design fine-tuning / multi-chain training |

The `info.csv` files index actual structure files (PDB, mmCIF) by relative path; the structure files themselves are also fetched by the download script.

## Production training recipe (sketch)

The published Genie 3 model was trained in stages:

1. **Pretraining** on AFDB representatives at L≤512, ~600k steps on 32 GPUs.
2. **Multi-chain extension** on PiNDER for binder/multi-chain capability.

Reproducing the published checkpoint requires:
- Multi-node multi-GPU job (≥32 GPUs)
- Several weeks of compute
- W&B for run tracking (or `--test` for local-only)

See the preprint (DOI 10.64898/2026.05.01.722168) §A for full hyperparameters.

## Local smoke test (single GPU)

```bash
genie3 train --config configs/training/smoke.yaml --devices 1 --test
```

`--test` disables remote logging so you don't need W&B credentials. Use a tiny `info.csv` subset for the smoke test.

## Distributed setup

- **Single node, multi-GPU**: `--devices N` with `--num-nodes 1`.
- **Multi-node SSH**: Lightning's default DDP launcher; configure `MASTER_ADDR`/`MASTER_PORT` per Lightning docs.
- **MPI cluster**: pass `--mpi-plugin` to use Lightning's MPI environment.

## Resuming and restoring

By default, training resumes from the latest checkpoint in the run's output dir. The dataloader state is also checkpointed. Use `--reset-dataloader-state` to discard the dataloader checkpoint (e.g. after switching dataset versions).

## Memory debugging

`--memory-snapshot` enables `torch.cuda.memory._record_memory_history()` and dumps a snapshot at exit. Open the resulting `.pickle` with PyTorch's memory visualizer to find leaks or fragmentation.

## Programmatic entry

`genie3.generation.workflow:run_training(config_path, devices, num_nodes, test, mpi_plugin, memory_snapshot, reset_dataloader_state)` is the function the CLI invokes. You can call it from Python if you need to embed training in a larger pipeline.
