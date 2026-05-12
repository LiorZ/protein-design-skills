# Extending RFD3 and RF3

Both `rfd3` and `rf3` are Hydra-driven; new behavior is configured via YAML, not by editing the CLI shim. The `rfd3 design` / `rf3 fold` commands just collect `key=value` overrides from argv and pass them to `compose(config_name="inference", overrides=args)`.

## RFD3

CLI: `models/rfd3/src/rfd3/cli.py`  
Configs: `models/rfd3/configs/`

```
configs/
├── inference.yaml             # top-level: pulls in inference_engine/rfdiffusion3 by default
├── inference_engine/
│   ├── base.yaml              # ckpt_path, out_dir, diffusion args, sampler args
│   ├── rfdiffusion3.yaml      # _target_: rfd3.engine.RFD3InferenceEngine
│   └── dev.yaml
├── experiment/                # debug.yaml, pretrain.yaml, test-uncond.yaml, test-unindexed.yaml
├── model/ trainer/ logger/ dataloader/ datasets/ callbacks/ debug/ paths/ hydra/
└── train.yaml validate.yaml
```

`inference.yaml`:

```yaml
# @package _global_
hydra:
  searchpath:
    - pkg://rfd3.configs
    - pkg://configs

defaults:
  - inference_engine: rfdiffusion3
  - _self_
```

### Add a new inference engine variant

1. Create `models/rfd3/configs/inference_engine/my_variant.yaml`:

   ```yaml
   # @package _global_
   defaults:
     - base
     - _self_

   _target_: rfd3.engine.RFD3InferenceEngine    # or your subclass
   out_dir: ???
   inputs: ???
   ckpt_path: rfd3                              # registered name or absolute path

   diffusion_batch_size: 8
   n_batches: 1

   inference_sampler:
     kind: "default"                            # or "symmetry"
     # ... override any field from base
   ```

2. Run with `rfd3 design inference_engine=my_variant inputs=spec.json out_dir=out/`.

If you also need a new *engine class* (not just config), add the class in `models/rfd3/src/rfd3/engine.py` (or a new module) and point `_target_` at it.

### Override fields inline

Anything in the YAML is overridable on the command line:

```bash
rfd3 design \
    inputs=spec.json out_dir=out/ \
    diffusion_batch_size=4 \
    inference_sampler.num_timesteps=50 \
    inference_sampler.cfg_scale=2.0 \
    dump_trajectories=True
```

## RF3

CLI: `models/rf3/src/rf3/cli.py` (commands: `fold`, `predict`, ...)  
Configs: `models/rf3/configs/`

```
configs/
├── inference.yaml
├── inference_engine/
│   ├── base.yaml              # ckpt_path, num_nodes/devices_per_node, dump_* flags
│   └── rf3.yaml               # _target_: rf3.inference_engines.rf3.RF3InferenceEngine
├── experiment/ model/ trainer/ logger/ dataloader/ datasets/ callbacks/ debug/ paths/ hydra/
└── train.yaml validate.yaml
```

`rf3.yaml` lists the runtime knobs that matter for most folds:

- `n_recycles`, `num_steps`, `diffusion_batch_size`
- `early_stopping_plddt_threshold`, `seed`, `verbose`
- `template_noise_scale`, `raise_if_missing_msa_for_protein_of_length_n`
- `metrics_cfg.*` — Hydra-instantiated metrics modules (pTM, ipTM, clashing chains, etc.)

### Add a new RF3 variant

Same pattern as RFD3:

1. Create `models/rf3/configs/inference_engine/my_variant.yaml` (`defaults: [base, _self_]`).
2. Either keep `_target_: rf3.inference_engines.rf3.RF3InferenceEngine` and only change runtime fields, or add a subclass and point `_target_` at it.
3. Run with `rf3 fold inference_engine=my_variant inputs=...`.

### Two CLI styles

Both forms are accepted by `rf3 fold`:

```bash
rf3 fold inputs=complex.json                    # plain
rf3 fold complex.json                           # single positional ⇒ becomes inputs=complex.json
rf3 fold inputs=protein.json msa_path=aln.a3m   # Hydra overrides
```

## When NOT to add a new config

If you're tweaking inference for a one-off run, prefer inline overrides over committing a new YAML — Hydra's compose handles arbitrarily deep `dotted.path=value` overrides, so a permanent file is only worth it for a stable, named recipe (e.g., "default symmetry sampler", "high-confidence binder validation").
