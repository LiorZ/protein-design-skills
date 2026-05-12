# Example experiment configs

These are unmodified copies of the configs shipped under
`<genie3-repo>/examples/`. Paths inside (`paths.rootdir`,
`paths.dataset`) are written relative to the repo root, so run them with
your shell's CWD at the repo root:

```bash
cd /path/to/genie3
conda activate genie3
genie3 run -c skill/examples/unconditional.yaml
```

| File | Application | Notes |
|------|-------------|-------|
| `unconditional.yaml` | Unconditional | 5 samples at length 50; ESMFold eval |
| `unconditional_legacy.yaml` | Unconditional | Loads Genie 2 backbone-only checkpoint |
| `motif_scaffolding.yaml` | Motif scaffolding | MotifBench `22_1BCF`, 5 samples |
| `motif_scaffolding_legacy.yaml` | Motif scaffolding | Genie 2 checkpoint |
| `binder_design.yaml` | Binder design | BinderBench `01_bhrf1`, 5 samples, ColabFold template mode |
| `binder_design_beam.yaml` | Binder design (beam) | Beam search width 4 |
| `binder_design_iterative.yaml` | Binder design (iterative) | 3 rounds: extended → iter_common → iter_common |

To run on N GPUs:

```bash
genie3 run -c skill/examples/binder_design.yaml --num-devices 4
```

To shard across nodes, see `references/multi-node.md`.

When adapting these for your own runs:
- Change `experiment.name` (used in log dir naming).
- Change `paths.rootdir` (output location).
- Bump `n_sample` (5 is just a smoke-test value).
- Adjust `direction_scale` per the cheat sheet in `references/configuration.md`.
