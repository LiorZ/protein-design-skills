# Steering — physical realism + collective-variable targeting

Steering guides the diffusion denoiser using **potential energy
functions** applied during each denoising step. Two built-in
algorithms; both are configured via a **single self-contained Hydra
YAML** passed as `--denoiser_config`.

```bash
python -m bioemu.sample \
    --sequence <aa> --num_samples N --output_dir <dir> \
    --denoiser_config <your_steering.yaml>
```

## SMC vs FKC — which to use

| Algorithm | Module | Default in | Best for |
|-----------|--------|-----------|----------|
| **SMC** (Sequential Monte Carlo) | `bioemu.steering.dpm_smc.dpm_solver_smc` | `physical_steering.yaml` | **Physical realism** — chain-break / clash avoidance. Candidates are denoised **unbiased**; resampled between particles by potential favorability. |
| **FKC** (Feynman–Kac Corrector) | `bioemu.steering.dpm_fkc.dpm_solver_fkc` | `cv_steer.yaml` | **Targeting a collective-variable value** (e.g. RMSD ≈ X). Candidates are denoised **with bias** from the reward; importance-weighted with optional ESS-based resampling. |

Rule of thumb from the upstream README: **3 to 10 particles** per
output sample is the empirical sweet spot. Wall-clock scales linearly
with `num_particles`.

## YAML schema

A steering YAML has four top-level groups:

```yaml
_target_: bioemu.steering.dpm_smc.dpm_solver_smc    # or dpm_fkc.dpm_solver_fkc
_partial_: true                                      # required (Hydra partial-instantiate)

# Denoiser hyperparameters
eps_t: 0.001          # diffusion end time
max_t: 0.99           # diffusion start time
N: 100                # number of denoising steps
noise: 0.5            # noise scale (SMC default 0.5; FKC default 1.0)
use_x0_for_reward: true   # FKC only — compute potentials at x0 instead of x_t

# List of potentials applied at every denoising step
fk_potentials:
  - _target_: bioemu.steering.UmbrellaPotential
    cv:
      _target_: bioemu.steering.CaCaDistance
    target: 0.38      # nm
    flatbottom: 0.1   # half-width of the zero-penalty zone
    slope: 10.0
    order: 1
    linear_from: 0.1
    weight: 1.0
  # …add more…

# How the particles are managed
steering_config:
  num_particles: 5
  ess_threshold: 0.5
  start: 0.1          # diffusion time to START steering (reverse goes 1→0)
  end: 0.0            # diffusion time to STOP steering
```

`start` / `end` are **diffusion times** in [0, 1] where the reverse
process flows from 1 (pure noise) to 0 (clean structure). `start=0.1,
end=0.0` means "steer only during the last 10% of denoising" — late
steering is the SMC default and the gentlest. `start=1.0, end=0.0`
(FKC default for CV) steers throughout.

## Available collective variables

All live under `bioemu.steering`:

| CV | Args | Returns | What it captures |
|----|------|---------|------------------|
| `CaCaDistance` | (none) | shape `(B, L-1)` Cα-Cα distances (nm) per consecutive pair | Chain integrity — large values = chain break |
| `PairwiseClash` | `min_dist=0.41`, `offset=3` | shape `(B,)` clash count (atom pairs within `min_dist` excluding within-`offset` neighbours) | Steric overlap — non-zero = clash |
| `RMSD` | `reference_pdb: <path>` | shape `(B,)` RMSD to reference (nm) | Distance from a known conformation. Used for FKC targeting. |

## Available potentials

| Potential | YAML key fields | Behavior |
|-----------|-----------------|----------|
| `UmbrellaPotential` | `target`, `flatbottom`, `slope`, `order`, `linear_from`, `weight` | Soft target. Zero penalty inside `target ± flatbottom`; grows as `slope × (|cv - target| - flatbottom)^order` outside, switching to linear past `linear_from`. Used for soft-but-firm "stay near target" steering. |
| `LinearPotential` | `target`, `slope`, `order`, `weight`, `clip_min`, `clip_max` | Linear reward / penalty around `target` with sign given by `slope` (negative = reward closer values). Used for CV-targeting where you want a smooth, unbounded gradient. |

## The two shipped configs

### `physical_steering.yaml` — production default for long chains

Combines two `UmbrellaPotential`s:

```yaml
fk_potentials:
  - UmbrellaPotential(cv=CaCaDistance, target=0.38, flatbottom=0.1, slope=10.0, order=1, linear_from=0.1, weight=1.0)
  - UmbrellaPotential(cv=PairwiseClash(min_dist=0.41, offset=3), target=0.0, flatbottom=0.0, slope=30.0, weight=1.0)
steering_config: { num_particles: 5, ess_threshold: 0.5, start: 0.1, end: 0.0 }
```

`target=0.38 nm` ≈ 3.8 Å is the canonical peptide Cα–Cα distance.
`PairwiseClash` is targeted to 0 (no clashes). `start=0.1, end=0.0`
means steering kicks in only during the last 10% of denoising —
gentle, cheap.

Use it for any sequence > ~100 aa, especially with disordered regions.

### `cv_steer.yaml` — bias toward a reference structure

```yaml
_target_: bioemu.steering.dpm_fkc.dpm_solver_fkc
noise: 1.0
use_x0_for_reward: true
fk_potentials:
  - LinearPotential(cv=RMSD(reference_pdb=???), target=0.5, slope=-7.4,
                    order=1, weight=1.0, clip_min=-0.5, clip_max=0.7)
steering_config: { num_particles: 100, ess_threshold: 0.7, start: 1.0, end: 0.0 }
```

`target=0.5 nm` = 5 Å, `slope=-7.4` means lower RMSD is rewarded.
**`reference_pdb` is a Hydra placeholder (`???`) — override on the CLI**:

```bash
python -m bioemu.sample \
    --sequence GYDPETGTWG --num_samples 100 --output_dir ~/cv-test \
    --denoiser_config src/bioemu/config/steering/cv_steer.yaml \
    +denoiser_config.fk_potentials.0.cv.reference_pdb=/abs/path/ref.pdb
```

Or copy the file, edit `reference_pdb:`, and point at your copy.

`num_particles=100` is much higher here because FKC importance
weights need a wide particle pool to find rare CV values without
collapsing. Wall-clock scales accordingly — expect ~100× the
unsteered cost.

## Writing your own

The Hydra `_target_` / `_partial_` pattern lets you compose any
combination. Example — bias toward Cα–Cα = 0.38 *and* target a
specific radius of gyration (would require writing a custom CV
subclass under `bioemu.steering`):

```yaml
_target_: bioemu.steering.dpm_smc.dpm_solver_smc
_partial_: true
eps_t: 0.001
max_t: 0.99
N: 100
noise: 0.5
fk_potentials:
  - _target_: bioemu.steering.UmbrellaPotential
    cv: { _target_: bioemu.steering.CaCaDistance }
    target: 0.38
    flatbottom: 0.1
    slope: 10.0
    order: 1
    linear_from: 0.1
    weight: 1.0
  - _target_: bioemu.steering.UmbrellaPotential
    cv: { _target_: bioemu.steering.PairwiseClash, min_dist: 0.41, offset: 3 }
    target: 0.0
    flatbottom: 0.0
    slope: 30.0
    weight: 1.0
  # Custom CV / potential go here
steering_config:
  num_particles: 10
  ess_threshold: 0.5
  start: 0.2          # earlier start → stronger steering, more cost
  end: 0.0
```

Each `fk_potential` is summed at every denoising step; their `weight`
field is the multiplier. Negative `slope` on a `LinearPotential` =
reward; positive = penalty.

## When NOT to steer

- Short, well-folded sequences (e.g. chignolin) where the unsteered
  filter already keeps most samples — adds cost for little gain.
- Free-energy / stability work where the unbiased Boltzmann
  distribution is the target. Physical steering biases toward chain
  integrity which is mostly a no-op for folded states but can subtly
  perturb the ratio of folded:unfolded states.
- FKC CV targeting where you want the *unbiased* ratio of basins —
  CV steering rewards proximity to the target value, so the resulting
  ensemble is **not** Boltzmann-distributed. Use only when you want
  the ensemble *in a basin*, not when you want the ratio between basins.
