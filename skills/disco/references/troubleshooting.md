# Troubleshooting

A catalogue of failure modes and fixes for DISCO inference.

## Install / startup

### `AssertionError: if use ds4sci, set env as https://www.deepspeed.ai/tutorials/ds4sci_evoformerattention/`

**Cause:** DISCO's default uses DeepSpeed4Science EvoformerAttention,
which needs CUTLASS on disk. `CUTLASS_PATH` is unset.

**Fix:** either
```bash
git clone https://github.com/NVIDIA/cutlass.git /path/to/cutlass
export CUTLASS_PATH=/path/to/cutlass
```
or pass `use_deepspeed_evo_attention=false` and accept slower / heavier
attention.

### `RuntimeError: CUDA error: no kernel image is available for execution on the device`

**Cause:** Your GPU is pre-Ampere (Turing, Pascal, Volta).
EvoformerAttention kernels are compiled for `8.0,8.9` (the runner sets
`TORCH_CUDA_ARCH_LIST=8.0,8.9`).

**Fix:** pass `use_deepspeed_evo_attention=false`.

### `uv sync` fails on `deepspeed`

**Cause:** AMD GPU; DeepSpeed has no AMD wheel.

**Fix:** delete the `deepspeed>=0.18.3` line from `pyproject.toml`, then
re-run `uv sync`. Add `use_deepspeed_evo_attention=false` to every
inference command.

### First run hangs for 5–10 minutes with no log output

**Cause:** Pairformer / EvoformerAttention kernels are JIT-compiling on
first call. CUTLASS compile is slow.

**Fix:** wait. The compile is cached for subsequent runs. If it takes
>30 minutes, abort and check `nvidia-smi` to confirm the GPU is
actually busy.

### `huggingface_hub.utils.HfHubHTTPError` while downloading `DISCO.pt`

**Cause:** Network blocked or HF rate-limited.

**Fix:** download the checkpoint manually:

```bash
huggingface-cli download DISCO-Design/DISCO DISCO.pt
```

Then pass it explicitly:

```bash
python runner/inference.py load_checkpoint_path=/path/to/DISCO.pt ...
```

### `Skipping 'foo.bar': not found or shape changed (saved (X,) → current (Y,))`

**Cause:** Custom checkpoint has a mismatched parameter.

**Fix:** if intentional (finetuned head, etc.), set `load_strict=false`
to allow it. Otherwise inspect the checkpoint vs. the current config —
something diverged.

## Input parsing

### `entity type must be proteinChain, dnaSequence, rnaSequence, ligand or ion`

**Cause:** Typo in the entity key (e.g. `protein` instead of
`proteinChain`, or `dna` instead of `dnaSequence`).

**Fix:** Use the exact camelCase keys. See [inputs.md](inputs.md).

### `Conformer generation failed for input SMILES: ...`

**Cause:** RDKit's `AllChem.EmbedMolecule` couldn't 3D-embed the SMILES
(common for very flexible or unusually-bonded molecules).

**Fix:** pre-generate a conformer externally and pass as `FILE_`:

```bash
obabel -ismi -ocan -O conformer.sdf --gen3D <<< "your_smiles"
```

then in the JSON:

```json
{"ligand": {"ligand": "FILE_/abs/path/conformer.sdf", "count": 1}}
```

### `too many smiles ligands`

**Cause:** More than 99 SMILES-style ligands across the entire input
file. SMILES ligands get residue names `l01`–`l99` to avoid clashing
with CCD codes.

**Fix:** split your input JSON into multiple files, each <100 SMILES
ligands. Or convert some to CCD codes / SDF files.

### `No atom found for <NAME> in entity <N> at position <P>`

**Cause:** A `covalent_bonds` entry references an atom that doesn't
exist. Likely:

- Wrong CCD atom name (case-sensitive; `SG` not `sg`).
- Wrong residue position (1-indexed; position counts include masked `-`).
- Wrong entity index (1-indexed in the order of `sequences`).
- For SMILES atom-map references: the SMILES doesn't have that atom map.

**Fix:** verify against the actual CCD entry for that residue.

### `Can not create bonds because the "count" of entity X and Y are not equal`

**Cause:** A covalent bond spans entities with different `count`.

**Fix:** make `count` equal on both endpoints. If you want N independent
ligands but only 1 protein, declare N separate `ligand` entries with
`count: 1` rather than one with `count: N`.

### File-format errors on `FILE_`-prefixed ligand path

**Cause:** Unsupported format (XYZ), or 2D-only SDF / MOL.

**Fix:** convert to a 3D SDF with Open Babel:

```bash
obabel input.xyz -O output.sdf --gen3d
```

Verify the SDF has non-trivial Z-coordinates before running DISCO.

## Runtime

### `torch.cuda.OutOfMemoryError`

Drill-down checklist:

1. Reduce protein length: e.g., from 300 → 200.
2. Reduce ligand atom count (some heavy macrocycles can be split or
   simplified).
3. Lower `effort` to `fast`.
4. Disable noisy guidance: `sample_diffusion.noisy_guidance.enabled=false`.
5. Ensure DeepSpeed EvoformerAttention is on (requires CUTLASS +
   Ampere+ NVIDIA). If you're stuck on the naive attention fallback,
   you'll OOM at much shorter sequences.
6. Use a bigger card (A100/H100/L40S with 40–80 GB).

### `RuntimeError: shape mismatch` in `load_state_dict`

**Cause:** Custom checkpoint architecture differs from current config.

**Fix:** set `load_strict=false`. If many params are skipped, your
checkpoint is for a different model — re-check `model.default` config.

### Inference is *much* slower than expected

Diagnose:

- Is `use_deepspeed_evo_attention` actually on? Look at the printed
  config tree at startup.
- Is `dtype=bf16` (default)? `fp32` will be slower.
- Is the GPU memory full? OOM cascades into slow swapping on some
  systems.
- Is the dataloader the bottleneck? `num_workers=0` is the default
  (fine for inference). Anything else can paradoxically slow.
- Is your CPU pegged on `RDKit.EmbedMolecule` for many SMILES ligands?
  Pre-embed offline.

### `AssertionError` on the line `assert ret_code == 0, f"Conformer generation failed for input SMILES: {smiles}"`

Same as the conformer-generation failure above. The SMILES could not be
embedded by RDKit.

## Output

### `path/to/output/sequences/<name>_sample_<seed>.txt does not exist!`

**Cause:** The sequence write was attempted but `os.fsync` saw an empty
file. Likely a disk-full or NFS-flush issue.

**Fix:** verify disk space, check NFS mount options, ensure the file
system isn't read-only.

### Output PDB has no ligand atoms even though I asked for one

Check:

- The job's `sequences` list does have a `ligand` (or `ion`) entry.
- The ligand's SDF was actually 3D (open it in PyMOL to confirm).
- The output PDB is the *DISCO* PDB — not a refolded one from a different
  predictor.

### `_ligands.txt` is missing

This file is **only written when the parser detects a non-CCD ligand**
(SMILES or `FILE_`). CCD-only jobs don't get one.

### Sequence file has weird lines I don't recognize

The format is **FASTA-ish, not strict FASTA**. It mixes:

- `>cogen_seq i` headers
- protein sequence lines
- `dna_sequence ...` lines
- `rna_sequence ...` lines
- `ligand_smiles ...` lines

Parse by line prefix. See [outputs.md](outputs.md) for a parser
snippet.

## Run-resume

### A whole run re-generated even though I just want to add seeds

**Cause:** You renamed jobs or changed `dump_dir`. The skip-check is
`<dump_dir>/<name>_sample_<seed>.pdb`. Renaming the job invalidates
that path.

**Fix:** keep `name` stable when iterating. Change `seeds=` and keep
`dump_dir=` to add samples incrementally.

### I changed flags but DISCO still uses old samples

**Cause:** Run-resume is **filename-based**. Flag changes don't
invalidate cached outputs.

**Fix:** either:
- `rm output/pdbs/<name>_sample_<seed>.pdb output/sequences/...` to
  force re-generation, or
- use a fresh `dump_dir=./new_out` for the new config.

## Distributed

### One rank crashes and the whole job dies

That's how DDP works. Re-launch the same command; run-resume keeps
completed samples and the unfinished ones retry.

### Some ranks finish much earlier than others

Sample distribution is per-job-per-seed. If you have many short jobs
and one long job, the rank that pulls the long one will lag. Reorder
jobs in the JSON or split into multiple files for more even load.

### `RuntimeError: Address already in use` at startup

DDP port collision (default `29500`). Set
`MASTER_PORT=29501` (or any free port) before launching.

## Reproducibility

### Same seed gives different outputs

Check:

- `deterministic=true` (the default).
- The same `experiment` and `effort` presets.
- The same checkpoint (`DISCO.pt` from HF, or your explicit
  `load_checkpoint_path`).
- The same CUDA / cuDNN / PyTorch versions. Cross-version
  reproducibility isn't guaranteed.

DDP introduces minor non-determinism unless you also pin
`torch.use_deterministic_algorithms(True)` and the CUBLAS workspace —
DISCO doesn't do this by default beyond `deterministic=true`.

## Performance reference

A100 80GB, length 200 protein, 1 SMILES ligand of ~30 heavy atoms:

| Effort | Guidance | Time / sample |
|--------|----------|--------------:|
| `fast` | off (`diverse`) | ~25 s |
| `fast` | on (`designable`) | ~40 s |
| `max` | off (`diverse`) | ~60 s |
| `max` | on (`designable`) | ~90 s |

Times scale roughly linearly with length and superlinearly with ligand
heavy-atom count. Older / smaller cards (L40S, 4090) are ~1.5–2× slower.
