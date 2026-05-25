# The `protenix` CLI

Installed as a console script (`protenix = runner.batch_inference:protenix_cli`).
Inside the SIF it's the default entrypoint, so `apptainer/run_protenix.sh <args>`
and `apptainer run protenix.sif <args>` both forward to `protenix <args>`.

```
protenix --help
protenix <subcommand> --help        # -h / --help on any subcommand
```

Subcommands:

| Name | Function | Input |
|------|----------|-------|
| `pred` | Structure prediction (the main command) | JSON file or directory |
| `json` | Convert PDB/CIF → Protenix input JSON | PDB/CIF file or directory |
| `msa`  | MSA search (MMseqs2), write paths into JSON | JSON or FASTA |
| `mt`   | MSA search **then** template search | JSON |
| `prep` | MSA + template + RNA-MSA (full preprocess) | JSON |

All commands accept a **directory** for `-i` and process every matching file in
it (`pred`/`msa` → `*.json`, `json` → `*.pdb`/`*.cif`). `-o/--out_dir` defaults
to `./output`.

---

## `protenix pred`

Run inference. A single runner is built once, then every JSON under `-i` is
MSA/template-preprocessed (unless paths are already present) and predicted.

```bash
apptainer/run_protenix.sh pred \
    -i examples/input.json -o ./output \
    -n protenix_base_default_v1.0.0 \
    --use_default_params true \
    --seeds 101,102 --sample 5
```

### Core options

| Flag | Default | Meaning |
|------|---------|---------|
| `-i, --input` | *(required)* | Input JSON file **or** directory of `*.json` |
| `-o, --out_dir` | `./output` | Output directory |
| `-n, --model_name` | `protenix_base_default_v1.0.0` | Checkpoint name (see `models.md`) |
| `--use_default_params` | `false` | **Set `true`**: forces the model's recommended `cycle`/`step` (and `use_msa=false` for ESM/ISM). Errors on an unknown model name. |
| `-s, --seeds` | `101` | Comma-separated integer seeds, e.g. `101,102,103`. One sub-dir per seed. |
| `-e, --sample` | `5` | Diffusion samples per seed (N structures each). |
| `-c, --cycle` | `10` | Pairformer recycle iterations. Overridden by `--use_default_params`. |
| `-p, --step` | `200` | Diffusion sampling steps. Overridden by `--use_default_params`. |
| `-d, --dtype` | `bf16` | Inference precision: `bf16` or `fp32`. |

> **Effect of `--use_default_params true`:** base / 20250630 / v0.5.0 / constraint
> / v2 → `cycle=10, step=200`; mini / tiny → `cycle=4, step=5`; mini-esm /
> mini-ism → also `use_msa=false`. Always prefer this over hand-setting cycle/step.

### Feature toggles

| Flag | Default | Meaning |
|------|---------|---------|
| `--use_msa` | `true` | Use protein MSA. If the JSON has no MSA paths, an MMseqs2 search runs automatically. Set `false` for single-sequence. |
| `--use_template` | `false` | Use structural templates. **Only** `protenix_base_default_v1.0.0`, `protenix_base_20250630_v1.0.0`, `protenix-v2`. Auto-searches if no `templatesPath` in the JSON. Needs `kalign`. |
| `--use_rna_msa` | `false` | Use RNA MSA. Same three models only. Auto-searches if no path. |
| `--use_seeds_in_json` | `false` | Use `modelSeeds` from the JSON instead of `--seeds`. |
| `--need_atom_confidence` | `false` | Also emit per-atom confidence in the output. |
| `--use_tfg_guidance` | `false` | Training-Free Guidance during diffusion. |
| `--msa_server_mode` | `protenix` | MSA backend: `protenix` or `colabfold`. |

### Performance / kernel selectors

These pick CUDA kernel implementations; defaults are tuned and rarely need
changing. Fall back to `torch` if a kernel fails on your GPU (see
`troubleshooting.md`).

| Flag | Default | Options |
|------|---------|---------|
| `--trimul_kernel` | `cuequivariance` | `cuequivariance`, `torch` |
| `--triatt_kernel` | `cuequivariance` | `triattention`, `cuequivariance`, `deepspeed`, `torch` |
| `--enable_cache` | `true` | Cache shareable vars in the diffusion module |
| `--enable_fusion` | `true` | Efficient kernel fusion in the diffusion transformer |
| `--enable_tf32` | `true` | TF32 for FP32 matmuls |

> The `deepspeed` triangle-attention kernel needs `CUTLASS_PATH` set (the image
> sets `/opt/cutlass`). On consumer GPUs (RTX 3090/4090) the custom Triton
> kernel falls back to PyTorch automatically (CHANGELOG issue #185).

### Template / RNA-MSA tool paths

Used only when the corresponding search runs and the binaries/DBs aren't on
`PATH`/defaults. The SIF installs `hmmer` and `kalign`.

`--kalign_binary_path`, `--hmmsearch_binary_path`, `--hmmbuild_binary_path`,
`--seqres_database_path` (template search); `--nhmmer_binary_path`,
`--hmmalign_binary_path`, `--hmmbuild_rna_binary_path`, `--ntrna_database_path`,
`--rfam_database_path`, `--rna_central_database_path`, `--nhmmer_n_cpu` (RNA MSA).

---

## `protenix json` — PDB/CIF → input JSON

Generate a ready-to-predict input JSON from an existing structure (re-fold an
experimental complex, or template a new job).

```bash
apptainer/run_protenix.sh json -i 7pzb.pdb -o ./jsons
apptainer/run_protenix.sh json -i ./cifs/ -o ./jsons --assembly_id 1
```

| Flag | Default | Meaning |
|------|---------|---------|
| `-i, --input` | *(required)* | PDB/CIF file or directory |
| `-o, --out_dir` | `./output` | Where to write `<name>.json` |
| `--altloc` | `first` | Alt-loc to keep: `first`, or a letter (`A`, `B`, …) |
| `--assembly_id` | `None` | Expand to this biological assembly (default: no expansion) |
| `--include_discont_poly_poly_bonds` | off | Include discontinuous polymer–polymer bonds |

PDB inputs are converted to CIF internally first. Output base name is the file
stem (truncated to 20 chars).

---

## `protenix msa` — MSA search only

```bash
apptainer/run_protenix.sh msa -i job.json -o ./msa_out      # updates JSON in place-ish
apptainer/run_protenix.sh msa -i seqs.fasta -o ./msa_out    # per-sequence MSA dirs
```

`-i` accepts a `.json` (returns an MSA-updated JSON path) or a `.fasta` (returns
a dict of sequence → MSA dir). `-m/--msa_server_mode` is `protenix` or
`colabfold`. Run this ahead of time to cache MSAs, then point `pred` at the
updated JSON.

## `protenix mt` — MSA + template search

```bash
apptainer/run_protenix.sh mt -i examples/example_without_msa.json -o ./output
```

JSON only. Adds `pairedMsaPath`/`unpairedMsaPath` then `templatesPath`. Same
hmmsearch/hmmbuild/seqres path flags as `pred`.

## `protenix prep` — full preprocess (MSA + template + RNA MSA)

```bash
apptainer/run_protenix.sh prep -i examples/examples_with_rna_msa/example_9gmw_2.json -o ./output
```

JSON only. Runs protein MSA, then template, then RNA-MSA search and writes a
`*-final-updated.json`. To force a fresh search, remove existing
`unpairedMsaPath` fields first. Accepts all hmmer/RNA-DB path flags.

---

## Splitting preprocess from prediction

For clusters, it's often best to run the (CPU-heavy, network-bound) MSA/template
search on a prep node and the (GPU-bound) prediction separately:

```bash
# 1) CPU node: search MSAs/templates -> writes an updated JSON
apptainer/run_protenix.sh prep -i job.json -o ./prep

# 2) GPU node: predict from the updated JSON, MSA already cached
apptainer/run_protenix.sh pred -i ./prep/job-final-updated.json -o ./out \
    -n protenix_base_default_v1.0.0 --use_default_params true
```

## Legacy / non-CLI entrypoint

`runner/inference.py` (run via `python runner/inference.py --input_json_path ...
--load_checkpoint_path ...`) is the lower-level runner the CLI wraps, and
`inference_demo.sh` / `train_demo.sh` / `finetune_demo.sh` are example driver
scripts in the repo. Prefer the `protenix` CLI for inference.
</content>
