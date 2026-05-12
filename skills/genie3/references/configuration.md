# Experiment YAML Schema

A single experiment YAML drives both generation and evaluation. The loader is
in `src/genie3/config/loader.py`; the typed dataclasses are in
`src/genie3/config/models.py`.

## Top-level structure

```yaml
experiment:        # required: identity
paths:             # output + dataset paths
generation:        # generation/sampling config (required for run/generate)
evaluation:        # evaluation config (required for run/evaluate)
runtime:           # optional: device counts, workers
rounds:            # optional: list of iterative rounds
```

## Sections

### `experiment` (required)

```yaml
experiment:
  name: my_run        # required, non-empty string; used in the log dir name
  seed: 0             # optional integer (reproducibility)
```

Unknown keys are kept in `experiment.extra`.

### `paths`

```yaml
paths:
  rootdir: outputs/run1   # output root for everything (generation + evaluation)
  dataset: data/design/binder_design/binderbench   # dataset root for motif/binder runs
```

Validation:
- `paths.rootdir` (or legacy `paths.outdir`) is **required** unless you set `generation.io.outdir` directly. Setting both with conflicting values raises `ConfigError`.
- `paths.dataset` is required when `generation.dataset.source` is `motif` or `target`.

### `generation`

```yaml
generation:
  base:                  # optional; defaults below
    checkpoint: pretrained/v1/checkpoints/step=600000.ckpt
    config:     pretrained/v1/config.yaml
  compile: false         # optional bool; enables torch.compile on the denoiser (recommended for beam search)
  dataset:
    source: <unconditional | motif | target | sidechain>   # required
    n_sample: <INT>                                        # required (per length / per problem)
    batch_size: 1                                          # default 1
    # ... source-specific keys (see below)
  io:
    outdir: <PATH>       # optional; falls back to paths.rootdir
    # ... extra IO keys passed through
  inference:             # OR use top-level `generation.sampler`/`search`/`reward` shorthand
    sampler:
      name: ddim         # default if omitted
      sampler:
        direction_scale: <FLOAT>   # see Application docs for tuning
        # ... other sampler-specific keys
    search:              # OPTIONAL: beam search (binder design)
      name: beam
      search:
        beam_width: 4          # default
        score_interval: 25     # default
        n_output: -1           # default (= beam_width)
        branch_noise_scale: 0.0
    reward:              # OPTIONAL: reward model for beam search
      name: colabfold
      reward:
        version: binder        # default
        mode: template         # default
        num_models: 1
        num_recycles: 3
        use_proteinmpnn: true
```

Loader-applied defaults:
- `base.checkpoint` defaults to `pretrained/v1/checkpoints/step=600000.ckpt`
- `base.config` defaults to `pretrained/v1/config.yaml`
- `dataset.batch_size` defaults to `1`
- `inference.sampler.name` defaults to `ddim`
- For `search.name == beam`: `beam_width=4, score_interval=25, n_output=-1, branch_noise_scale=0.0`
- For `reward.name == colabfold`: `version=binder, mode=template, num_models=1, num_recycles=3, use_proteinmpnn=true`

Forbidden keys:
- `generation.dataset.datadir` — use `paths.dataset` instead
- `reward.reward.datadir` — use `paths.dataset` instead
- `generation.io.outdir` conflicting with `paths.rootdir` — pick one

Shorthand accepted:
- `generation.sampler:` at top level is moved into `generation.inference.sampler` (raises `ConfigError` if both are set).

#### `generation.dataset` per source

**`source: unconditional`**
```yaml
dataset:
  source: unconditional
  min_length: 50
  max_length: 300
  length_step: 50
  n_sample: 50           # per length
```

**`source: motif`**
```yaml
dataset:
  source: motif
  selections: 22_1BCF,01_1LDB    # optional CSV of problem names
  tags: easy                     # optional CSV of tags from problem JSON
  n_sample: 100                  # per problem
```
The dataset is the directory pointed to by `paths.dataset` (must contain `problems/*.json` and `motifs/*.pdb`).

**`source: target`** (binder design)
```yaml
dataset:
  source: target
  selections: 01_bhrf1,02_sc2rbd # optional CSV
  tags: AlphaProteo              # optional CSV
  n_sample: 200                  # per problem
  cond_strategy: hotspot         # see iterative-and-beam.md
```

`cond_strategy` options:
- `hotspot` — minimal hotspot residues from problem JSON
- `extended` — extended interface from problem JSON (computed by `compute_extended_interface`)
- `common` — user-provided `common` interface from problem JSON
- `iter_common` — *iterative*: computes common interface from prior rounds' v0 successes
- `iter_common_prob` — like `iter_common` but probabilistic per-trajectory sampling

### `evaluation`

```yaml
evaluation:
  version: <unconditional | scaffold | binder>   # required for run/evaluate
  verbose: false
  inverse_folding:
    mode: all                # default
    model_name: proteinmpnn  # or `forward` (forward-fold scoring)
    num_seq: 8               # default; set to 1 for fast binder runs
  folding:
    mode: template           # `template` (no MSA), `msa`, or `single` (model-specific)
    model_name: colabfold    # or `esmfold`, `boltz2`
    backend: subprocess      # default
    num_models: 5            # ColabFold ensemble size; 1 in beam-search reward
    num_recycles: 20         # ColabFold recycles; 3 in beam-search reward
  reduction:
    calc_novelty: false      # if true, computes novelty vs training set (slower)
    skip_reduce: false       # if true, halts before reduce (useful for sharded eval)
```

Defaults applied by `_parse_evaluation`:
- `inverse_folding.mode = all`
- `inverse_folding.model_name = proteinmpnn`
- `inverse_folding.num_seq = 8`
- `folding.mode = template`
- `folding.model_name = colabfold`
- `folding.backend = subprocess`
- `folding.num_models = 5`
- `folding.num_recycles = 20`

`evaluation.version` selects the reducer (`UnconditionalReducer`, `ScaffoldReducer`, `BinderReducer`) and how `info.csv` columns + success filters are computed. See [outputs.md](outputs.md).

### `runtime`

```yaml
runtime:
  num_devices: 1     # GPUs per process (overridden by --num-devices)
  device: null       # explicit torch device string
  workers: null      # dataloader workers
```

`num_nodes` is no longer a runtime field (each invocation is single-node; use `--shard-id`/`--num-shards` for multi-node).

### `rounds` (iterative binder design)

```yaml
rounds:
  - id: round_0
    cond_strategy: extended
  - id: round_1
    cond_strategy: iter_common
    n_sample: 16        # optional override of dataset.n_sample for this round only
```

Each `round` requires `cond_strategy`. `id` defaults to `round_<i>`. See [iterative-and-beam.md](iterative-and-beam.md) for full semantics.

## Sampler `direction_scale` cheat sheet

Controls the classifier-free-guidance-like quality/diversity trade-off:

| Application | Length | Recommended `direction_scale` |
|-------------|--------|-------------------------------|
| Unconditional | ≤ 300 (short monomers) | `0.8` |
| Unconditional | > 300 (long monomers) | `0.0` |
| Motif scaffolding | any | `0.1` |
| Binder design | any | `0.0` |

Higher values bias toward higher-confidence (lower-diversity) samples. Tuning above the recommended values is the easiest way to trade diversity for quality on short proteins.

## Worked examples

### Unconditional (sweep lengths 50–300, 50 samples each, 4 GPUs)

```yaml
experiment: { name: uncond_sweep }
paths:      { rootdir: out/uncond_sweep }

generation:
  dataset:
    source: unconditional
    min_length: 50
    max_length: 300
    length_step: 50
    n_sample: 50
  sampler:
    sampler:
      direction_scale: 0.8

evaluation:
  version: unconditional
  folding:
    model_name: esmfold

runtime:
  num_devices: 4
```

Run: `genie3 run -c uncond_sweep.yaml`.

### Motif scaffolding (one MotifBench problem)

```yaml
experiment: { name: scaffold_22_1BCF }
paths:
  rootdir: out/scaffold
  dataset: data/design/motif_scaffolding/motifbench

generation:
  dataset:
    source: motif
    selections: 22_1BCF
    n_sample: 100
  sampler:
    sampler:
      direction_scale: 0.1

evaluation:
  version: scaffold
  folding:
    model_name: esmfold
```

### Binder design (single problem, ColabFold template)

```yaml
experiment: { name: binder_bhrf1 }
paths:
  rootdir: out/binder_bhrf1
  dataset: data/design/binder_design/binderbench

generation:
  dataset:
    source: target
    selections: 01_bhrf1
    n_sample: 200
  sampler:
    sampler:
      direction_scale: 0.0

evaluation:
  version: binder
  inverse_folding:
    num_seq: 1                  # 1 sequence per backbone (default 8 is slow)
  folding:
    model_name: colabfold
    mode: template              # no MSA
```

## Validation errors

The loader raises `ConfigError` (subclass of `Exception`) for:
- Missing `experiment.name`
- Both `paths.rootdir` and `paths.outdir` set with different values
- Both `generation.io.outdir` and `paths.rootdir` set with different values
- Both `generation.sampler` and `generation.inference.sampler` set
- `generation.dataset.datadir` or `reward.reward.datadir` explicitly set
- Missing `generation.dataset.source` or `generation.inference.sampler`
- `evaluation.version` missing for `run`/`evaluate`
- `paths.rootdir` missing when `evaluate` is invoked

## Where defaults live

If you change a default, edit `_parse_generation` / `_parse_evaluation` in `src/genie3/config/loader.py`. The dataclasses (`GenerationConfig`, `EvaluationConfig`, etc.) carry the dataclass-level defaults; the loader fills in framework-level defaults like the pretrained checkpoint path and the beam-search hyperparameters.
