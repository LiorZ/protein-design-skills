# Beam Search and Iterative Binder Design

Two advanced binder-design pipelines built on top of the basic `target` workflow:

- **Beam search** — branch N parallel diffusion trajectories per sample, score them with ColabFold at fixed checkpoints, keep the top N. Improves per-sample quality at higher compute cost.
- **Iterative design** — run multiple rounds of generate→evaluate, where each round's interface conditioning is computed from prior rounds' successes. Converges the conditioning toward what actually works.

The two compose: a single experiment can have both `inference.search:` and `rounds:`.

## Beam search

### Quick start

```bash
genie3 run -c examples/binder_design/experiment_beam.yaml --num-devices 4
```

### Config

```yaml
experiment: { name: binder_beam }
paths:
  rootdir: out/binder_beam
  dataset: data/design/binder_design/binderbench

generation:
  compile: true                # torch.compile the denoiser (recommended)
  dataset:
    source: target
    selections: 01_bhrf1
    n_sample: 200              # total designs you want
  inference:
    sampler:
      sampler:
        direction_scale: 0.0
    search:
      name: beam
      search:
        beam_width: 4          # branches per checkpoint (default 4)
        score_interval: 25     # steps between rescoring (default 25)
        n_output: -1           # outputs per run (default -1 → equals beam_width)
        branch_noise_scale: 0.0
    reward:
      name: colabfold
      reward:
        version: binder        # default
        mode: template         # template | msa
        num_models: 1          # default
        num_recycles: 3        # default
        use_proteinmpnn: true  # use ProteinMPNN to assign sequences before scoring

evaluation:
  version: binder
  inverse_folding:
    model_name: forward        # forward-fold scoring (faster than full ProteinMPNN)
  folding:
    model_name: colabfold
    mode: template
```

### How `n_sample` is interpreted in beam mode

`n_sample` in the config is the **total number of output designs you want**. The loader auto-converts:

```
outputs_per_run = beam_width  if n_output <= 0  else n_output
run_count       = ceil(n_sample / outputs_per_run)
```

It then sets `dataset.n_sample = run_count` (number of beam-search runs to launch) and stores the original `n_sample` as `search.requested_n_sample` so the beam runner can trim the final run if needed.

For example: `n_sample: 200, beam_width: 4, n_output: -1` → 50 beam-search runs, each producing 4 outputs.

### When sharded

Beam runs are split per shard:

```
runs_per_shard  = ceil(run_count / num_shards)
shard's runs    = [shard_id * runs_per_shard, shard_id * runs_per_shard + runs_per_shard)
search.requested_n_sample is preserved globally
```

Sample IDs in `info.csv` are globally indexed (e.g. `sample_399` from shard 7 of 8) so the final reduce step concatenates cleanly.

### When to use beam search

- Hard targets where naive sampling has very low V0 success rates
- When you have GPU budget for the per-checkpoint ColabFold rescoring
- When you can tolerate `compile: true`'s warmup cost (a few minutes per run)

For most easy/medium targets, plain sampling with more `n_sample` is more cost-efficient.

## Iterative design

### Quick start

```bash
genie3 run -c examples/binder_design/experiment_iterative.yaml --num-devices 4
```

Re-running the same command resumes from the last incomplete round.

### Config

```yaml
experiment: { name: binder_iter }
paths:
  rootdir: out/binder_iter
  dataset: data/design/binder_design/binderbench

generation:
  dataset:
    source: target
    selections: 01_bhrf1
    n_sample: 8              # default per-round; round can override
  sampler:
    sampler:
      direction_scale: 0.0

evaluation:
  version: binder
  inverse_folding: { num_seq: 1 }
  folding:
    model_name: colabfold
    mode: template

rounds:
  - id: round_0
    cond_strategy: extended
  - id: round_1
    cond_strategy: iter_common
  - id: round_2
    cond_strategy: iter_common
    n_sample: 16             # optional: override n_sample for this round
```

### How rounds execute

For each round, `_run_iterative` in `cli.py`:

1. Checks `<rootdir>/<round_id>/.generate_done` and `.evaluate_done` sentinels — skips a round if both exist.
2. If `cond_strategy in {iter_common, iter_common_prob}`:
   - Loads each problem JSON (from `<rootdir>/problems/<problem>.json` if it exists, else from the original dataset).
   - Globs `<prior_round>/<problem>/results/v0_success/successful_complexes/*.pdb` across all completed rounds.
   - Calls `compute_common_interface_from_filepaths` and writes `target_interface_residues.<cond_strategy>_round<N>` into the per-problem JSON cache at `<rootdir>/problems/<problem>.json`.
   - Sets the round's `cond_strategy` to that resolved key (e.g. `iter_common_round0`).
3. Builds a per-round YAML (in `tempfile.NamedTemporaryFile(suffix='.yaml')`) with:
   - `paths.rootdir = <rootdir>/<round_id>`
   - `paths.dataset = <rootdir>` if iter strategy (so the cached problems dir is read), else original dataset
   - `generation.dataset.cond_strategy = <resolved>`
   - `generation.dataset.n_sample = round.n_sample` if set
   - `rounds:` removed (so the child does not recurse)
   - `generation.io.outdir` cleared (so it falls back to `paths.rootdir`)
4. Runs three child stages: `generate`, `evaluate`, `evaluate --reduce`.
5. Touches `.generate_done` and `.evaluate_done` sentinels in `<rootdir>/<round_id>/`.

### `cond_strategy` semantics in iterative mode

| Strategy | Where it reads from |
|----------|---------------------|
| `hotspot` | `target_interface_residues.hotspot` in the original problem JSON |
| `extended` | `target_interface_residues.extended` (precomputed by `prepare.py`) |
| `common` | `target_interface_residues.common` (user-provided) |
| `iter_common` | Computed: intersection-style "common" interface from all prior rounds' V0 successes |
| `iter_common_prob` | Computed: probabilistic — each trajectory samples residues proportional to their frequency in prior successes; hotspots are always included |

`iter_common_prob` injects diversity across trajectories within a round; `iter_common` is deterministic (same conditioning for every sample).

### Iter cache layout

After running iterative rounds, you'll have:

```
<rootdir>/
  problems/                            # cached, accumulating problem JSONs
    01_bhrf1.json                      # extra keys: iter_common_round0, iter_common_round1, ...
  round_0/
    01_bhrf1/results/v0_success/successful_complexes/*.pdb
    .generate_done
    .evaluate_done
  round_1/
    01_bhrf1/results/v0_success/successful_complexes/*.pdb
    .generate_done
    .evaluate_done
  round_2/
    ...
```

The cached `problems/<key>.json` is the dataset for round 1 onward when an iter strategy is used.

### Status

```bash
genie3 status -c <CFG>
```

Prints one row per round:

```
✅ round_0       [extended]            generate ✅   evaluate ✅
🟡 round_1       [iter_common]         generate ✅   evaluate ⬜
🔵 round_2       [iter_common]         generate ⬜   evaluate ⬜
```

### When to use iterative

- Multi-week production binder campaigns
- When V0 hit rates in round 0 are nonzero but low
- When you want to converge interface conditioning toward what successful designs actually engage

If round 0 produces zero V0 successes, `iter_common*` cannot compute conditioning and emits a warning — fall back to `extended` or `common` for the next round.

## Combining beam + iterative

You can stack: each iterative round can use beam-search internally. Add `inference.search: { name: beam }` and `inference.reward: { name: colabfold }` to the *base* `generation` block; per-round overrides only touch `cond_strategy` and `n_sample`. Compute cost multiplies — start with `beam_width: 4`, `n_sample: 8`, 2 rounds before scaling up.
