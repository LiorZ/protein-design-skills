# CLI reference

`boltzgen` is the single console entry point. It dispatches to six
subcommands.

```
boltzgen [-v|--version] {run, configure, execute, check, download, merge}
```

---

## `boltzgen run`

The main pipeline. Reads one or more design YAMLs and produces a ranked,
filtered design set.

```
boltzgen run SPEC [SPEC …] [--output OUT] [--protocol P]
                  [--num_designs N] [--budget B] [--alpha A]
                  [--steps STEPS …] [--reuse]
                  [--devices N] [--num_workers N]
                  [--cache PATH] [--moldir M]
                  [--config STEP arg=val …]
                  [--diffusion_batch_size N] [--design_checkpoints C …]
                  [--step_scale X] [--noise_scale X]
                  [--inverse_fold_num_sequences K] [--inverse_fold_checkpoint C]
                  [--inverse_fold_avoid LETTERS] [--skip_inverse_folding]
                  [--only_inverse_fold]
                  [--folding_checkpoint C] [--affinity_checkpoint C]
                  [--filter_biased true|false]
                  [--metrics_override k=w …] [--additional_filters 'k>v' …]
                  [--size_buckets MIN-MAX:N …]
                  [--refolding_rmsd_threshold X]
                  [--no_subprocess]
                  [--use_kernels auto|true|false]
                  [--force_download] [--models_token T] [--config_dir D]
```

### Positional

| Argument      | Meaning                                                                                       |
|---------------|-----------------------------------------------------------------------------------------------|
| `SPEC` (1+)   | Path(s) to `.yaml` design spec(s). For a single shared target with many scaffolds, pass several. Multiple specs are concatenated into the same run. Also accepts a directory pre-configured by `boltzgen configure`. |

### General configuration

| Flag                          | Default                | Meaning                                                                                                  |
|-------------------------------|------------------------|----------------------------------------------------------------------------------------------------------|
| `--protocol P`                | `protein-anything`     | One of `protein-anything`, `peptide-anything`, `protein-small_molecule`, `nanobody-anything`, `antibody-anything`, `protein-redesign`. Selects defaults & steps. |
| `--output PATH`               | (required for run-flow)| Output directory. Reused across runs (see `--reuse`).                                                    |
| `--config STEP k=v …`         | —                      | Override Hydra config of a step. Example: `--config folding num_workers=4 trainer.devices=4 data.cfg.batch_size=2`. Can be repeated; one `--config` block per step. |
| `--devices N`                 | all CUDA devices       | GPUs per step (DDP via PyTorch-Lightning).                                                                |
| `--num_workers N`             | 1                      | DataLoader workers per step.                                                                              |
| `--config_dir D`              | `src/boltzgen/resources/config` | Override the default Hydra config dir.                                                          |
| `--use_kernels {auto,true,false}` | `auto`             | cuEquivariance kernels. `auto` enables when CUDA capability ≥ 8.                                          |
| `--moldir M`                  | `huggingface:boltzgen/inference-data:mols.zip` | Reference moldir.                                                                    |
| `--reuse`                     | off                    | Re-attach to an existing `--output`; only the missing designs are generated.                              |

### Design step

| Flag                          | Default                                | Meaning                                                                                              |
|-------------------------------|----------------------------------------|------------------------------------------------------------------------------------------------------|
| `--num_designs N`             | 10000                                  | Total intermediate designs (before filtering down to `--budget`).                                    |
| `--diffusion_batch_size N`    | 1 if N<100 else 10                     | Diffusion samples per trunk run. All designs in a batch share the same sampled length.               |
| `--design_checkpoints C …`    | `boltzgen1_diverse.ckpt boltzgen1_adherence.ckpt` | One or more checkpoints; each runs an equal fraction of designs.                          |
| `--step_scale X`              | scheduled (default schedule)           | Fixed step scale (e.g., 1.8). Disables the schedule.                                                 |
| `--noise_scale X`             | scheduled (default schedule)           | Fixed noise scale (e.g., 0.98). Disables the schedule.                                               |

### Inverse-folding step

| Flag                              | Default                                | Meaning                                                                                              |
|-----------------------------------|----------------------------------------|------------------------------------------------------------------------------------------------------|
| `--skip_inverse_folding`          | off                                    | Use diffusion-generated sequence directly without IF.                                                 |
| `--inverse_fold_num_sequences K`  | 1                                      | Number of sequences per backbone (raises diversity at this stage).                                    |
| `--inverse_fold_checkpoint C`     | `boltzgen1_ifold.ckpt`                 | Path / HF locator for the IF checkpoint.                                                              |
| `--inverse_fold_avoid LETTERS`    | none / `C` for peptide/antibody/nanobody | Forbid certain residues at IF time (e.g., `KEC`).                                                  |
| `--only_inverse_fold`             | off                                    | Skip diffusion — IF an existing fully-specified structure end-to-end (replaces ProteinMPNN).          |

### Folding + affinity steps

| Flag                              | Default                                | Meaning                                                                                              |
|-----------------------------------|----------------------------------------|------------------------------------------------------------------------------------------------------|
| `--folding_checkpoint C`          | `boltz2_conf_final.ckpt`               | Boltz-2 refolding checkpoint.                                                                        |
| `--affinity_checkpoint C`         | `boltz2_aff.ckpt`                      | Boltz-2 affinity head (only used under `protein-small_molecule`).                                    |

### Filtering step

| Flag                              | Default                                | Meaning                                                                                              |
|-----------------------------------|----------------------------------------|------------------------------------------------------------------------------------------------------|
| `--budget B`                      | 30                                     | Size of the final diversity-optimized set.                                                            |
| `--alpha A`                       | 0.001 (0.01 for `peptide-anything`)    | Quality-vs-diversity for the final set selection: 0=quality only, 1=diversity only.                  |
| `--filter_biased {true,false}`    | `true`                                 | Remove ALA / GLY / GLU / LEU / VAL composition outliers.                                              |
| `--metrics_override k=w …`        | none                                   | Per-metric inverse-importance weights for ranking. Larger weight = *less* important. `k=none` drops the metric. |
| `--additional_filters 'k>v' …`    | none                                   | Hard filters; `>` for higher-is-better, `<` for lower-is-better. **Single-quote** in shell.            |
| `--size_buckets MIN-MAX:N …`      | none                                   | Cap final set per length bucket, e.g. `10-20:5 20-30:10 30-40:5`.                                     |
| `--refolding_rmsd_threshold X`    | (protocol default; 2 for peptide)      | Pass / fail RMSD threshold; lower is better.                                                          |

### Execution + model download

| Flag                          | Default          | Meaning                                                                                          |
|-------------------------------|------------------|--------------------------------------------------------------------------------------------------|
| `--no_subprocess`             | off              | Run each step in the same process. Breaks `--devices > 1`. Use only when debugging.              |
| `--steps STEP …`              | all              | Subset of `{design, inverse_folding, design_folding, folding, affinity, analysis, filtering}`.    |
| `--force_download`            | off              | Re-download weights even if cached.                                                              |
| `--models_token T`            | hard-coded HF token | Hugging Face token for the weights repo.                                                       |
| `--cache PATH`                | `~/.cache`       | Where downloaded models live.                                                                    |

---

## `boltzgen check`

Validate one or more YAML specs and (optionally) emit colored mmCIFs so
you can verify in Molstar that your binding sites, design regions,
structure-group visibility, etc. are what you intended. No GPU work.

```
boltzgen check SPEC [SPEC …] [--output DIR] [--moldir M]
                    [--force_download] [--models_token T] [--cache PATH]
```

| Flag         | Meaning                                                                                |
|--------------|----------------------------------------------------------------------------------------|
| `--output D` | Write `<spec_stem>.cif` per input spec. If omitted, only validation runs.              |
| `--moldir M` | Reference moldir (same default as `run`).                                              |

Recommended habit: run `boltzgen check` on every new YAML and open the
resulting CIF in https://molstar.org/viewer/ before launching a campaign.

---

## `boltzgen configure`

Resolve every step's Hydra config and write them to `--output`, but
don't run anything. You can then edit the configs by hand and run
`boltzgen execute`.

```
boltzgen configure SPEC [SPEC …] --output DIR [--steps STEP …]
                                  [same general/design/IF/folding/filtering
                                   flags as `run`]
```

Almost everything that `run` accepts is also accepted by `configure`.
The only thing missing is `--no_subprocess` (configure always writes
configs only; execute is what runs them).

---

## `boltzgen execute`

Run a pipeline whose Hydra configs already live in a directory (typically
produced by `configure`).

```
boltzgen execute OUT_DIR [--no_subprocess] [--steps STEP …]
```

Useful for "I want to hand-edit one Hydra knob without re-running
configure" or "I want to run the same pre-baked config on a SLURM
worker without re-running configure inside the job".

---

## `boltzgen download`

Pre-fetch any subset of artifacts. Not normally needed.

```
boltzgen download {affinity, design-adherence, design-diverse, folding,
                   inverse-fold, moldir, all} […]
                  [--force_download] [--models_token T] [--cache PATH]
```

`boltzgen download all` is the right move before going offline / on an
air-gapped HPC node.

---

## `boltzgen merge`

Combine the design / IF / folding / analysis outputs from several
parallel `run` outputs so you can run `--steps filtering` on the union.

```
boltzgen merge SOURCE [SOURCE …] --output DIR
```

Each `SOURCE` must be a finished pipeline output (`run` or `execute`).
After merging, run filtering on the merged dir:

```
boltzgen run SPEC --steps filtering --output DIR --protocol P [--budget …] [--alpha …]
```

See `references/slurm.md` for the canonical "job-array × N + merge +
filter" pattern.

---

## `--config` examples

Anything that lives in a step's Hydra config can be overridden:

```bash
# More workers for folding
boltzgen run SPEC --config folding num_workers=4

# 4 GPUs on every step, plus a non-default trainer precision
boltzgen run SPEC \
  --config design trainer.devices=4 trainer.precision=bf16-mixed \
  --config folding trainer.devices=4 \
  --config inverse_folding trainer.devices=4 \
  --config analysis num_processes=64

# Override the dilated schedule in the design step (e.g., for new chemistry)
boltzgen run SPEC --config design \
  override.diffusion_process_args.sampling_schedule=uniform \
  override.diffusion_process_args.time_dilation=null
```

The "step names" you can pass to `--config` and `--steps` are exactly:
`design`, `inverse_folding`, `design_folding`, `folding`, `affinity`,
`analysis`, `filtering`. See `references/pipeline.md` for what each one
does.
