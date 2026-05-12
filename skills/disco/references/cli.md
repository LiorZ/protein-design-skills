# CLI reference — `runner/inference.py`

DISCO's CLI is a [Hydra](https://hydra.cc/) entry-point with
`config_path=../configs` and `config_name=inference.yaml`. Anything in
`configs/` can be overridden inline with `key=value`. This page documents
the full set of overrides you'll actually use.

## Invocation

```bash
python runner/inference.py [HYDRA OVERRIDES]
```

There are no `argparse`-style flags. Every option is a Hydra key.

## Top-level overrides

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `experiment` | enum | none | `designable` or `diverse`. Composes a preset YAML into the config. **Required for any non-default sampling strategy.** |
| `effort` | enum | `max` | `fast` or `max`. Sets diffusion-step count and recycling cycles. |
| `input_json_path` | path | `input_jsons/unconditional_config.json` | Input JSON describing jobs. |
| `seeds` | list[int] | `[101, 102]` | Random seeds. Total samples = `len(seeds) × len(jobs)`. |
| `num_inference_seeds` | int | `null` | If set, overrides `seeds` with `[0..N-1]`. |
| `dump_dir` | path | `./output` | Output root. PDBs / sequences / ERR all go under here. |
| `load_checkpoint_path` | path | `null` | Custom checkpoint. If null or missing, DISCO downloads `DISCO.pt` from HuggingFace. |
| `load_strict` | bool | `true` | If `false`, mismatched / extra state-dict keys are skipped (useful for finetuned ckpts). |
| `bb_only` | bool | `true` | Backbone-only token mask for outputs (centroid placement for ligand). |
| `deterministic` | bool | `true` | Force deterministic CUDA ops. |
| `dtype` | enum | `bf16` | Inference precision: `fp32`, `bf16`, or `fp16`. |
| `need_atom_confidence` | bool | `false` | Dump per-atom confidence next to predictions. |
| `output_format` | enum | `unconditional_monomer_protein` | `unconditional_monomer_protein` writes single-chain PDBs. `null` writes CIFs via the generic dumper (richer metadata, multi-entity). |
| `inference_loop_strategy_name` | str | `BasicInferenceLoopStrategy` | Internal loop strategy. Don't override. |
| `use_fabric` | bool | `true` | Use Lightning Fabric for DDP. |
| `eval_version` | enum | `unconditional` | Use `conditional_biomol` to force DNA/RNA annotation in the output sequence file even when the input has no nucleic-acid entity (rarely needed). |
| `infer_batch_size` | int | `1` | Tested only at 1. Do not change. |
| `n_seq_duplicates_per_structure` | int | `1` | Sample N sequence outputs per generated structure (writes `>cogen_seq 0..N-1` to the sequence file). |
| `shuffle_dataloader` | bool | `${gt:${fabric.num_nodes},1}` | Shuffles when multi-node. |
| `inference_random_transform_ref_pos` | bool | `true` | Randomize ligand reference pos transform. |
| `inference_random_transform_msk_res` | bool | `${task_manager.transform_masked_ref_pos}` | Randomize masked-residue ref pos. |
| `inference_ref_pos_augment` | bool | `${task_manager.ref_pos_augment}` | Apply ref-pos augmentation. |

## Model + diffusion overrides

These are inside the `model:` and `sample_diffusion:` config groups. They
control sampling speed / quality and the noisy-guidance behaviour.

### Trunk

| Key | Default | Meaning |
|-----|--------:|---------|
| `model.N_cycle` | `4` (max) / `2` (fast) | Trunk recycling cycles. Higher → better refinement, more compute. |
| `model.use_joint_diffusion_module` | `false` | Internal: joint vs disjoint diffusion module. Leave as-is. |
| `n_blocks` | `8` | Pairformer blocks (trunk depth). Fixed by checkpoint. |
| `model.pairformer.n_heads` | `16` | Pairformer attention heads. Fixed by checkpoint. |
| `model.pairformer.dropout` | `0.25` | Dropout (inference doesn't use it but config has it). |
| `model.diffusion_module.use_fine_grained_checkpoint` | `true` | Activation checkpointing inside the diffusion module. |
| `blocks_per_ckpt` | `1` | Number of blocks per activation-checkpoint block. `null` disables checkpointing. |
| `use_memory_efficient_kernel` | `false` | Internal flag. |
| `use_lma` | `false` | Use LMA (low-memory-attention). Not needed if EvoformerAttention is on. |
| `use_deepspeed_evo_attention` | `true` | DeepSpeed4Science EvoformerAttention. Requires CUTLASS + Ampere+ NVIDIA. |
| `dtype` | `bf16` | Inference precision. |

### Diffusion sampling

| Key | Default (max / fast) | Meaning |
|-----|---------------------:|---------|
| `sample_diffusion.N_step` | `200` / `100` | Diffusion sampling steps. |
| `sample_diffusion.gamma0` | `0.8` (designable) / `1.6` (diverse) | Initial gamma (noise scale). |
| `sample_diffusion.gamma_min` | `1.0` | Minimum gamma. |
| `sample_diffusion.gamma_anneal` | `none` | `none` / `linear` / `cosine`. Anneal gamma over the trajectory. |
| `sample_diffusion.noise_scale_lambda` | `1.003` (default) / `0.1` (presets override) | EDM noise multiplier λ. |
| `sample_diffusion.step_scale_eta` | `1.5` | EDM step-scale η. |
| `sample_diffusion.integrator` | `euler` | `euler` or `heun` (2nd-order, 2× NFE). |
| `inference_noise_scheduler.s_max` | `160.0` | Max σ in the EDM schedule. |
| `inference_noise_scheduler.s_min` | `4e-4` | Min σ. |
| `inference_noise_scheduler.rho` | `7.0` | EDM ρ exponent (preset overrides to `7.0`). |
| `inference_noise_scheduler.sigma_data` | `16.0` | EDM σ_data. |
| `inference_noise_scheduler.t_start` | `0.0` | Trajectory start time. |

### Noisy guidance (designable preset only by default)

| Key | Default (designable) | Meaning |
|-----|---------------------:|---------|
| `sample_diffusion.noisy_guidance.enabled` | `true` | Toggle the entire mechanism. |
| `sample_diffusion.noisy_guidance.guid_struct` | `true` | Enable structure guidance. |
| `sample_diffusion.noisy_guidance.guide_seq` | `true` | Enable sequence guidance. |
| `sample_diffusion.noisy_guidance.omega_struct` | `1.5` | Structure-guidance scale ω. |
| `sample_diffusion.noisy_guidance.omega_seq` | `2.0` | Sequence-guidance scale ω. |
| `sample_diffusion.noisy_guidance.rescale_phi` | `0.7` | Rescale factor φ for guidance. |
| `sample_diffusion.noisy_guidance.uncond_struct_time` | `0.8` | Unconditional-eval time for structure. |
| `sample_diffusion.noisy_guidance.uncond_seq_time` | `0.6` | Unconditional-eval time for sequence. |
| `sample_diffusion.noisy_guidance.guidance_start_frac` | `0.3` | Fraction of the trajectory at which guidance starts. |
| `sample_diffusion.noisy_guidance.guidance_end_frac` | `0.8` | Fraction at which guidance stops. |

Disable cheaply: `sample_diffusion.noisy_guidance.enabled=false`.

## Sequence sampling strategy

The `experiment=designable` / `experiment=diverse` presets both swap
the sampling strategy to **path planning**. The relevant knobs:

| Key | Default (designable / diverse) | Meaning |
|-----|-------------------------------:|---------|
| `sequence_sampling_strategy.score_type` | `random` | Path-planner score: `random` (default) or `entropy`. |
| `sequence_sampling_strategy.logits_temp` | `0.8` | Decoder logits temperature. |
| `sequence_sampling_strategy.score_temp` | `1.0` | Score temperature for path-planner. |
| `sequence_sampling_strategy.switch_temp` | `true` | Switch between temperatures during the trajectory. |
| `sequence_sampling_strategy.mask_stochasticity_strength` | `1.0` | Stochasticity in mask schedule. |
| `sequence_sampling_strategy.entropy_adaptive_temp` | `true` (designable) / `false` (diverse) | Per-position entropy-adaptive temperature (confident positions get T × (1+β)). |
| `sequence_sampling_strategy.entropy_adaptive_beta` | `1.0` | Strength β of entropy-adaptive scaling. 0 = disabled, 1 = paper. |
| `sequence_sampling_strategy.entropy_adaptive_anneal_power` | `0.0` | Anneal β over t_next: `0` = constant (default), `1` = linear, `2` = quadratic. |
| `sequence_sampling_strategy.allow_remasking` | `true` | Let the planner remask positions during sampling. |
| `sequence_sampling_strategy.should_ensure_unmasked_stay` | `false` | Prevent fixed residues from being remasked. |
| `sequence_sampling_strategy.planner_name` | `null` | Custom path planner — leave as-is. |
| `sequence_sampling_strategy.sequence_noise_scheduler.power` | `1.0` (designable) / `1.5` (diverse) | Power of the polynomial noise schedule. Higher → more aggressive masking schedule. |

## Distributed / multi-GPU

| Key | Default | Meaning |
|-----|--------:|---------|
| `fabric.num_nodes` | `1` | Number of nodes. >1 enables multi-node DDP (launch with `srun` / `torchrun`). |
| `num_workers` | `0` | DataLoader workers. |

DISCO uses Lightning Fabric with the `DDPStrategy(find_unused_parameters=False)`.
For single-node multi-GPU, launch with the standard PyTorch
distributed launcher and the runner shards the dataloader across ranks.

## Worked examples

### Unconditional, fast prototyping

```bash
python runner/inference.py \
  experiment=designable \
  effort=fast \
  input_json_path=input_jsons/unconditional_config.json \
  seeds=\[0,1,2,3,4\] \
  dump_dir=./prototyping
```

### Studio-179 single split, paper config

```bash
python runner/inference.py \
  experiment=diverse \
  effort=max \
  input_json_path=input_jsons/all_priorities_ligands_split_0.json \
  seeds=\[$(seq -s "," 0 4)\] \
  dump_dir=./studio179_split0
```

### 100 seeds per job (large screening), cheap-but-near-designable

```bash
python runner/inference.py \
  experiment=designable \
  effort=fast \
  sample_diffusion.noisy_guidance.enabled=false \
  input_json_path=input_jsons/your_screen.json \
  num_inference_seeds=100 \
  dump_dir=./screen
```

### Sequence ensemble per backbone

```bash
python runner/inference.py \
  experiment=diverse \
  effort=max \
  input_json_path=input_jsons/heme_b.json \
  seeds=\[0,1,2\] \
  n_seq_duplicates_per_structure=5 \
  dump_dir=./heme_seq_ensemble
```

Each `length_*_heme_b_sample_<seed>.txt` then contains 5 `>cogen_seq i`
records for the same backbone.

### Custom checkpoint

```bash
python runner/inference.py \
  experiment=designable \
  effort=max \
  load_checkpoint_path=/scratch/me/disco_finetuned.pt \
  load_strict=false \
  input_json_path=input_jsons/your_input.json \
  seeds=\[0,1,2,3\]
```

### AMD GPU / older NVIDIA

```bash
python runner/inference.py \
  experiment=designable \
  effort=fast \
  use_deepspeed_evo_attention=false \
  input_json_path=input_jsons/unconditional_config.json \
  seeds=\[0\] \
  dump_dir=./amd_out
```

### Multi-node SLURM (sketch)

```bash
srun --nodes=4 --ntasks-per-node=8 \
  python runner/inference.py \
    experiment=diverse \
    effort=max \
    fabric.num_nodes=4 \
    input_json_path=input_jsons/all_priorities_ligands_split_0.json \
    seeds=\[$(seq -s "," 0 99)\]
```

### Tuning sampling temperature for sequence diversity

Raise `logits_temp` for more sequence diversity; lower for more conservative,
high-likelihood residues:

```bash
python runner/inference.py \
  experiment=diverse \
  effort=max \
  sequence_sampling_strategy.logits_temp=1.2 \
  input_json_path=input_jsons/my_design.json \
  seeds=\[0,1,2,3,4\]
```

### Switching the integrator for higher-quality diffusion

```bash
python runner/inference.py \
  experiment=designable \
  effort=max \
  sample_diffusion.integrator=heun \
  input_json_path=input_jsons/my_design.json \
  seeds=\[0,1,2\]
```

Heun doubles the NFE per step — pair with a smaller `N_step` if you want
to keep total cost comparable.

## Tips

- **Quote the seed list.** Bash glob-expansion will eat the brackets. Use
  `seeds=\[0,1,2,3,4\]` or single-quote: `'seeds=[0,1,2,3,4]'`.
- **`$(seq -s , 0 N)`** is the standard idiom for big seed lists.
- **Hydra prints the full config tree** at startup (via `print_config_tree`)
  — read it once to confirm your overrides took effect.
- **All paths in `input_json_path`** can be relative to the DISCO repo
  root, even though Hydra changes the working directory at launch.
  `FILE_studio-179/priority_1/heme_b_final_0.sdf` still works.
