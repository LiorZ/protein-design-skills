# Presets — `experiment` and `effort`

DISCO has two preset axes:

1. **`experiment`** — the *sampling strategy* (designable vs diverse).
   This is the noisy-guidance / entropy-adaptive-temperature axis.
2. **`effort`** — the *compute budget* (fast vs max).
   This is the diffusion-steps / recycling-cycles axis.

You generally pick one of each per run.

## `experiment=designable`

What it does (from `configs/experiment/designable.yaml`):

- Sequence sampling: `path_planning` strategy, **entropy-adaptive
  temperature on** (β=1.0, switch-T enabled, logits T=0.8).
- Diffusion: **noisy guidance ON** for both structure (ω=1.5, φ=0.7) and
  sequence (ω=2.0). Guidance window: trajectory fraction 0.3–0.8.
  Unconditional eval times: structure 0.8, sequence 0.6.
- `N_step=200`, `N_cycle=4` (matches `effort=max`).
- `noise_scale_lambda=0.1`, `rho=7.0`.
- Sequence-noise polynomial scheduler `power=1.0`.

Effect: steers the model toward samples that are **likely to re-fold
correctly** under an external structure predictor (Chai-1, AF2). The
price is slightly less structural diversity.

**Use when:**
- You want unconditional samples that survive a refold filter.
- You're prototyping and want the highest hit rate of designable samples.

**Don't use when:**
- You're benchmarking against the paper's ligand or nucleic-acid
  numbers — those used `diverse`.
- You want to explore structural variety (large screens).

### Cheap-but-near-designable

The noisy guidance doubles the effective batch size of each diffusion
forward pass. To save ~50% inference cost at a ~10% co-designability cost:

```bash
python runner/inference.py \
  experiment=designable \
  effort=max \
  sample_diffusion.noisy_guidance.enabled=false \
  ...
```

This keeps entropy-adaptive temperature and the noise schedule but
turns off guidance. Recommended for large screening runs.

## `experiment=diverse`

What it does (from `configs/experiment/diverse.yaml`):

- Sequence sampling: `path_planning` strategy, **entropy-adaptive
  temperature off**, switch-T enabled, logits T=0.8.
- Diffusion: **noisy guidance OFF**.
- `gamma0=1.6` (higher initial gamma — more exploration early in the
  trajectory).
- `N_step=200`, `N_cycle=4`.
- `noise_scale_lambda=0.1`, `rho=7.0`.
- Sequence-noise polynomial scheduler `power=1.5` (more aggressive masking
  schedule).

Effect: samples more freely from the learned distribution → higher
structural variety, lower per-sample co-designability than `designable`,
but **higher *count* of diverse co-designable samples** in a large run.

**Use when:**
- You're doing ligand / DNA / RNA conditioning (paper default).
- You're running Studio-179 or any reproducibility benchmark.
- You want diverse hits, e.g. for catalysis where many local-fold
  solutions exist.

## `effort=fast`

| Knob | Value |
|------|------:|
| `sample_diffusion.N_step` | 100 |
| `model.N_cycle` | 2 |

~4× faster than `max`, ~10% drop in co-designability. **Recommended only
for unconditional generation** — the paper explicitly warns against
`fast` for conditional generation (ligand, DNA, RNA).

```bash
python runner/inference.py \
  experiment=designable \
  effort=fast \
  input_json_path=input_jsons/unconditional_config.json \
  seeds=\[0,1,2,3,4\]
```

## `effort=max`

| Knob | Value |
|------|------:|
| `sample_diffusion.N_step` | 200 |
| `model.N_cycle` | 4 |

Paper-quality, slower. **Always use this for conditional generation.**

```bash
python runner/inference.py \
  experiment=diverse \
  effort=max \
  input_json_path=input_jsons/heme_b.json \
  seeds=\[0,1,2,3,4\]
```

You can also override the underlying knobs directly:

```bash
model.N_cycle=3 sample_diffusion.N_step=150
```

For the ablations in the paper, anything beyond `N_step=100`, `N_cycle=2`
sees diminishing returns; the difference between `fast` and `max` is
mostly in the long-tail of difficult samples.

## Combination matrix

| Task | `experiment` | `effort` | Why |
|------|--------------|----------|-----|
| Unconditional, prototyping | `designable` | `fast` | Cheap, refoldable |
| Unconditional, paper-quality | `designable` | `max` | Best co-designability |
| Ligand-conditioned (any) | `diverse` | `max` | Paper default |
| DNA / RNA-conditioned | `diverse` | `max` | Paper default |
| Multi-cofactor / enzyme | `diverse` | `max` | Maximum exploration around the active site |
| Large screen, cost-sensitive | `designable` | `max` + `noisy_guidance.enabled=false` | 50% cheaper, near-designable |
| Length sweep + selection | `diverse` | `max` | Diversity over many lengths, downstream filter |
| Reproducing Studio-179 | `diverse` | `max` | Mandatory for comparability |
| Benchmarking *against* DISCO | `diverse` (conditional) or `designable` (unconditional) | `max` | Required for paper-quality numbers |

## Knob-level overrides

If you want to tweak presets:

```bash
# Diverse but with stronger sequence diversity:
python runner/inference.py \
  experiment=diverse \
  sequence_sampling_strategy.logits_temp=1.2 \
  sample_diffusion.gamma0=2.0 \
  ...

# Designable but with a wider guidance window:
python runner/inference.py \
  experiment=designable \
  sample_diffusion.noisy_guidance.guidance_start_frac=0.1 \
  sample_diffusion.noisy_guidance.guidance_end_frac=0.9 \
  ...
```

Hydra layers `experiment=X` first and then your overrides on top, so any
preset value can be cleanly replaced.
