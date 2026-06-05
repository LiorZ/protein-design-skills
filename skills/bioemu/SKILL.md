---
name: bioemu
description: >
  Run BioEmu (Biomolecular Emulator) — Microsoft Research's deep
  generative model that samples from the **approximated equilibrium
  (Boltzmann) distribution** of structures for a protein monomer, given
  its amino acid sequence. BioEmu is **not** a single-structure
  predictor: it's the AF3-class "many predictors" diffusion model whose
  output is an **ensemble** (an `.xtc` trajectory of backbone frames)
  approximating MD-style equilibrium, at orders-of-magnitude lower cost
  than running MD. Use this skill when:
  (1) Sampling a **conformational ensemble** of a protein monomer from
      its sequence (the headline use case — chignolin, folded/unfolded
      coexistence, fast-folder benchmarks, etc.),
  (2) Mapping **conformational changes** relevant to function —
      formation of **cryptic pockets**, local **unfolding** events,
      large-scale **domain rearrangements**,
  (3) Predicting **folding free energies / protein stability** (ΔG_fold)
      directly from the sampled ensemble (the v1.1 and v1.2 checkpoints
      were trained with experimental ΔG measurements via PPFT),
  (4) Emulating **MD-style equilibrium distributions** without paying
      the MD wall-clock — TICA / metastable-state analysis on the
      sampled `.xtc`,
  (5) Steering sampling toward **physically valid** structures (the
      default SMC steering with `physical_steering.yaml`: CaCa-distance
      umbrella + pairwise-clash penalty — dramatically reduces chain
      breaks and clashes for long / disordered chains),
  (6) Steering sampling toward a **collective-variable target** with
      the FKC sampler (`cv_steer.yaml` — e.g. RMSD to a reference PDB,
      to bias the ensemble toward a specific conformational basin),
  (7) Reconstructing **side chains** and running a short **MD
      equilibration** on samples (`bioemu.sidechain_relax` → HPacker for
      side-chain rebuilding + OpenMM local minimization or NVT
      equilibration),
  (8) Choosing the **right BioEmu checkpoint** — `v1.0` (preprint),
      `v1.1` (Science paper, **default**), `v1.2` (extended MD + 1.3M
      ΔG measurements + extra residue-type embeddings),
  (9) Bringing your **own MSA** (`.a3m`) or pointing at a custom MMseqs2
      `msa_host_url`, or caching ColabFold embeddings to disk
      (`cache_embeds_dir`),
  (10) Sizing **batch size for sequence length** (`batch_size_100=N`
       — BioEmu scales batch by `N × (100/L)²`; halve `batch_size_100`
       when you OOM on long sequences).

  Covers the pip install (Linux-only, Python ≥ 3.10, `pip install
  bioemu` or `pip install bioemu[cuda]` for JAX-CUDA12 MSA, optional
  `bioemu[md]` for OpenMM + HPacker), the bundled ColabFold + vendored
  AlphaFold2 (no separate install — first run downloads ~3.5 GB weights
  to `~/.cache/colabfold/`), the model weight zoo (auto-downloaded from
  `huggingface.co/microsoft/bioemu`), the `python -m bioemu.sample` CLI
  and the `from bioemu.sample import main as sample` Python API, the two
  built-in denoisers (`dpm` default + `heun`), the two steering
  algorithms (**SMC** for physical realism, **FKC** for collective-
  variable targeting) configured via a single Hydra YAML — including
  the four available CVs (`CaCaDistance`, `PairwiseClash`, `RMSD`)
  and two potentials (`UmbrellaPotential`, `LinearPotential`) — the
  output layout (`samples.xtc` + `topology.pdb` + `sequence.fasta` +
  per-batch `batch_*.npz`), the side-chain reconstruction +
  optional-MD-equil pipeline (`samples_sidechain_rec.{pdb,xtc}` and
  `samples_md_equil.{pdb,xtc}`), resumable runs (existing npz batches
  are detected and skipped to top up `num_samples`), Azure AI Foundry
  hosted endpoint (`Standard_NC24ads_A100_v4`), expected sampling times
  on A100 80 GB (~ 4 min / 40 min / 150 min for L=100 / 300 / 600 at
  1000 samples), and the model's hard limitations.

  Limitations: **monomers only** — multi-chain proteins, ligands, ions,
  DNA, and RNA are out of scope (the README explicitly suggests trying
  the linker trick for multimers but reports it has not worked well).
  Backbone-frame output only — side chains require the
  `sidechain_relax` module. Linux-only pip install. CUDA strongly
  recommended (CPU is technically supported but unusably slow).

  Pairs with: `boltz` / `chai-lab` / `protenix` / `esm-biohub` /
  `fair-esm` (single-structure predictors — BioEmu is the
  ensemble/dynamics counterpart for the same sequence; combine to get
  one "best" structure + the surrounding conformational fluctuations),
  `placer` (refine and score ligand poses + side chains in
  conformations BioEmu samples — useful for cryptic-pocket validation),
  `biotite` (parse `samples.xtc`, compute RMSF / SASA per frame, do
  TICA-style projection of the ensemble, cluster), `boltzgen` /
  `bindcraft` / `disco` / `genie3` / `foundry` (BioEmu is **not** a
  designer — design with these; then run BioEmu on your accepted
  designs to check the conformational stability you actually care about
  experimentally), `protflow` (orchestrate "design → BioEmu ensemble →
  ΔG-fold rank" as a SLURM array pipeline).
license: MIT
category: protein-design
tags: [protein-ensembles, equilibrium-distribution, conformational-sampling, diffusion, score-based, boltzmann-emulation, md-emulation, folding-free-energy, cryptic-pockets, steering, smc, fkc, hpacker, openmm, monomer]
repo: https://github.com/microsoft/bioemu
huggingface: https://huggingface.co/microsoft/bioemu
biorxiv: https://doi.org/10.1101/2024.12.05.626885
science: https://www.science.org/doi/10.1126/science.adv9817
azure: https://ai.azure.com/explore/models/BioEmu/version/1/registry/azureml
---

# BioEmu — biomolecular equilibrium ensemble emulator

## What this is

BioEmu is a **DiG-style score-based diffusion model** that, given a
protein monomer's amino acid sequence, samples from an approximation of
its **equilibrium (Boltzmann) distribution** of backbone structures.
The output is *not* a single predicted structure — it is an **ensemble**
(`samples.xtc`) of many backbone-frame conformations. It is the
ensemble / MD counterpart to AF3-class predictors:

| You want… | Use |
|-----------|-----|
| One **best** structure for a sequence (monomer / complex / ligand / nucleic acid) | `boltz`, `chai-lab`, `protenix`, `esm-biohub` (ESMFold2), `fair-esm` (ESMFold) |
| The **ensemble of structures** — conformational changes, cryptic pockets, folding/unfolding, free-energy landscape — for a **monomer** | **BioEmu** |
| Conformational sampling of an **interface / ligand / multimer** | Real MD (GROMACS/AMBER), or hybrid: ensemble for each monomer from BioEmu + dock with `placer` |
| Designed-binder **validation** (one shot) | `boltz` / `chai-lab` / `protenix` (and BindCraft already does AF2 reprediction) |
| Designed-binder **conformational stability** (does it stay folded? is the binding mode the only mode?) | BioEmu on the designed binder sequence |

Trained on AFDB + ~216 ms of MD + ~1.3M experimental folding ΔG
measurements, with Property-Prediction Fine-Tuning (PPFT) to match
experimental stabilities. Validated against millisecond-MD
distributions with ~0.9 kcal/mol MAE on free-energy errors and
~83% / 70-82% / 55-88% coverage of domain-motion / local-unfolding /
cryptic-pocket reference states.

## Hard limitations (read first)

- **Monomers only.** No multi-chain proteins, no ligands, no ions, no
  DNA, no RNA. The README explicitly says the "linker trick" for
  multimers has not worked well.
- **Backbone-frame output.** Side chains must be reconstructed
  separately (`bioemu.sidechain_relax` → HPacker).
- **Linux + pip only.** No Windows, no Docker image upstream.
- **GPU required in practice.** CPU works but is unusably slow.
- **No new sequences.** BioEmu does not design — it samples
  conformations for a fixed sequence.
- **Inherits AF2 + MD biases.** The training data is AFDB (AF2
  predictions) + simulated MD + experiment.

## Installation

```bash
# Base (CPU-only JAX for MSA / embedding extraction)
pip install bioemu

# Recommended: CUDA-accelerated MSA extraction
pip install bioemu[cuda]      # adds jax[cuda12]==0.4.35 + nvidia-cuda-nvcc-cu12

# Optional: side-chain reconstruction + MD relax (HPacker via conda, OpenMM)
pip install bioemu[md]        # adds openmm==8.4.0, openmm-cuda-12==8.4.0
```

Linux + Python ≥ 3.10. First sampling run downloads:

- **AlphaFold2 weights** (~3.5 GB) for the bundled inlined ColabFold MSA
  / embedding step → `~/.cache/colabfold/`.
- **BioEmu checkpoint** (`bioemu-v1.0`, `v1.1`, or `v1.2`) from
  `huggingface.co/microsoft/bioemu`.
- **HPacker** (first call to `sidechain_relax`) into a separate
  virtualenv — needs `conda` on PATH and CUDA 12.

No separate ColabFold / AlphaFold install — both are vendored
(`src/_vendor/alphafold/` + `src/bioemu/colabfold_inline/`).

Full hardware/version notes → `references/installation.md`.

## Quickstart — chignolin in 30 seconds

```bash
python -m bioemu.sample \
    --sequence GYDPETGTWG \
    --num_samples 10 \
    --output_dir ~/test-chignolin
```

Or via Python:

```python
from bioemu.sample import main as sample

sample(sequence='GYDPETGTWG', num_samples=10, output_dir='~/test_chignolin')
```

Outputs land in `~/test-chignolin/`:

```text
sequence.fasta        # the input sequence
topology.pdb          # backbone topology
samples.xtc           # the ensemble (≤ num_samples frames; some may be filtered)
batch_*.npz           # per-batch raw outputs (kept for resumability)
```

By default, unphysical samples (steric clashes, chain breaks) are
**filtered out** — so `samples.xtc` may have fewer frames than
`num_samples`. For long / disordered sequences you can lose a lot this
way; use `--filter_samples=False` to keep everything, or **enable
physical steering** (next section) to reduce unphysical samples at the
source.

## The five things you actually tune

| Knob | CLI flag | Python kwarg | When to change |
|------|----------|--------------|----------------|
| Sequence | `--sequence` | `sequence=` | The protein, as a string, FASTA path, or A3M file. A3M = bring-your-own MSA. |
| Sample count | `--num_samples` | `num_samples=` | Typically 100–1000 for a meaningful ensemble; 10000+ for free-energy work. |
| Output dir | `--output_dir` | `output_dir=` | **Re-running with the same dir resumes** — existing batches are detected and only the missing ones are sampled. |
| Batch size | `--batch_size_100` | `batch_size_100=` | Batch size *for an L=100 sequence*. Real batch = `batch_size_100 × (100/L)²` (quadratic in length). Default `10`; tune down to `5`/`3`/`1` if you OOM. |
| Model | `--model_name` | `model_name=` | `bioemu-v1.1` (default, Science paper) / `bioemu-v1.0` (preprint) / `bioemu-v1.2` (extended MD + ΔG). |

## Steering — physical realism + collective-variable targeting

Steering applies potential energy functions during denoising. Two
algorithms are built in:

| Algorithm | Module path | When |
|-----------|-------------|------|
| **SMC** (Sequential Monte Carlo) | `bioemu.steering.dpm_smc.dpm_solver_smc` | Default for **physical** steering (chain-break / clash avoidance). Candidates are denoised unbiased, then resampled by potential favorability. |
| **FKC** (Feynman–Kac Corrector) | `bioemu.steering.dpm_fkc.dpm_solver_fkc` | Default for **collective-variable** targeting (e.g. RMSD to a reference). Importance-weighted with optional ESS-based resampling; samples are denoised with bias from the reward. |

Configured via a **single Hydra YAML** passed as `--denoiser_config`
(it replaces the default denoiser entirely — no separate flag for the
sampler). Two configs ship:

```bash
# Physical realism (default SMC) — drastically fewer clashes / chain breaks
python -m bioemu.sample \
    --sequence GYDPETGTWG --num_samples 100 \
    --output_dir ~/steered-samples \
    --denoiser_config src/bioemu/config/steering/physical_steering.yaml

# Target a collective variable (RMSD to reference) — FKC
python -m bioemu.sample \
    --sequence GYDPETGTWG --num_samples 100 \
    --output_dir ~/cv-steered \
    --denoiser_config src/bioemu/config/steering/cv_steer.yaml \
    +denoiser_config.fk_potentials.0.cv.reference_pdb=/path/to/ref.pdb
```

The README's empirical guidance: **3 to 10 steering particles per
output sample** is the sweet spot. Wall-clock scales linearly with
`num_particles`; physical steering is almost always worth the cost on
sequences > ~100 aa.

Available building blocks (compose your own steering YAML):

| Kind | Class | Used for |
|------|-------|----------|
| Potential | `bioemu.steering.UmbrellaPotential` | Soft target with flat-bottom + slope — used for `CaCaDistance` and `PairwiseClash` |
| Potential | `bioemu.steering.LinearPotential` | Linear reward / penalty — used for CV targeting (RMSD) |
| CV | `bioemu.steering.CaCaDistance` | Cα–Cα bond distance (prevent chain breaks) |
| CV | `bioemu.steering.PairwiseClash` | Non-neighbour atom distances (prevent clashes) |
| CV | `bioemu.steering.RMSD` | RMSD vs a reference PDB |

Steering keys in the YAML's `steering_config:` block: `num_particles`,
`ess_threshold`, `start` / `end` (diffusion time range — note reverse
process goes 1→0). Full YAML schema and tuning → `references/steering.md`.

## Side chains and MD relax

BioEmu's core output is **backbone frames only**. To get all-heavy-atom
structures, run the bundled `sidechain_relax` module:

```bash
python -m bioemu.sidechain_relax \
    --pdb-path  ~/test-chignolin/topology.pdb \
    --xtc-path  ~/test-chignolin/samples.xtc \
    --outpath   ~/test-chignolin/relaxed
```

This produces (under `--outpath`, with prefix `samples` by default):
- `samples_sidechain_rec.{pdb,xtc}` — heavy-atom structures with
  HPacker-rebuilt side chains.
- `samples_md_equil.{pdb,xtc}` — same, after a short OpenMM local
  minimization (`local_minimization`, default) or NVT equilibration
  (`--md-protocol md_equil`, ~0.1 ns).

Options worth knowing:

| Flag | Default | Meaning |
|------|---------|---------|
| `--md-equil / --no-md-equil` | `--md-equil` | Whether to run MD equil after side-chain reconstruction |
| `--md-protocol` | `local_minimization` | `local_minimization` (fast, fixes clashes) or `md_equil` (slower, fixes worse issues; runs NVT then NPT, with backbone-constrained equilibration) |
| `--simtime-ns` | `0` | Free-MD time after equilibration (requires `md_equil`) |
| `--prefix` | `samples` | Output file prefix |

This module is **per-frame** — its wall-clock scales linearly with
`num_samples` and quadratically with sequence length. **Run it on a
subsample** (e.g. 10–50 frames) rather than the full ensemble unless
you specifically need every frame relaxed. Full reference →
`references/sidechain-relax.md`.

## Output layout

```text
<output_dir>/
├── sequence.fasta              # the input sequence
├── topology.pdb                # backbone topology (single frame, used as .xtc top)
├── samples.xtc                 # the ensemble — up to num_samples frames (may be fewer if filter_samples=True)
└── batch_*.npz                 # per-batch raw outputs; kept so re-running resumes
```

After `sidechain_relax` (using `--outpath` and default `prefix=samples`):

```text
<outpath>/
├── samples_sidechain_rec.pdb   # single-frame topology with side chains
├── samples_sidechain_rec.xtc   # full ensemble with side chains
├── samples_md_equil.pdb        # single-frame topology after MD equil
├── samples_md_equil.xtc        # full ensemble after MD equil
└── frame*_md_top.pdb           # per-frame MD topologies (only if simtime_ns > 0)
```

## Sampling-time budget (A100 80 GB, default `batch_size_100=20`, 1000 samples)

| Sequence length | Wall-clock |
|----------------:|-----------:|
| 100 | ~4 min |
| 300 | ~40 min |
| 600 | ~150 min |

Quadratic in length (memory **and** time). For longer proteins, lower
`batch_size_100` and budget more time.

## Key gotchas

1. **Monomers only.** Don't try multimers / ligands / nucleic acids.
   The model has no embeddings for them.
2. **`samples.xtc` may have fewer frames than `num_samples`** when
   `filter_samples=True` (default). For long / disordered chains, the
   loss can be large — turn on physical steering instead of disabling
   the filter.
3. **`batch_size_100` is a scaling constant, not the actual batch
   size.** Real batch = `batch_size_100 × (100/L)²`. Default 10 →
   actual batch = 10 at L=100, ≈ 1 at L=300, ≈ 0 (= 1) at L=600. On
   small GPUs at long lengths, drop `batch_size_100` to 3–5 to be safe.
4. **Re-running resumes.** Same `output_dir` = continue. Existing
   `batch_*.npz` files are detected and only the missing ones are
   sampled. To start from scratch, delete the batches first.
5. **`base_seed` is set from system time by default.** For reproducible
   ensembles, pin `base_seed=<int>`. Each batch uses
   `base_seed + start_idx`.
6. **A3M input bypasses the ColabFold server.** Pass an `.a3m` path
   to `--sequence` to use your own MSA; `msa_host_url` is ignored.
7. **HPacker first-call setup needs conda + CUDA 12.** If you don't
   have conda on PATH, `sidechain_relax` will fail at first invocation
   — set `HPACKER_PYTHONBIN=/path/to/python` to bypass the auto-setup.
8. **Steering YAMLs are *self-contained denoiser configs*.** Passing
   `--denoiser_config <steering.yaml>` replaces the entire denoiser —
   you don't also pass `--denoiser_type`. The default `dpm.yaml` /
   `heun.yaml` are *unsteered* denoiser configs; the steering YAMLs
   wrap `dpm_solver_smc` / `dpm_solver_fkc` instead.
9. **`cv_steer.yaml` requires `reference_pdb`.** The shipped file has
   `???` as a Hydra placeholder — override on the CLI with
   `+denoiser_config.fk_potentials.0.cv.reference_pdb=/abs/path/ref.pdb`
   or copy the YAML and edit the field.
10. **The `bioemu-v1.1` checkpoint is the default.** Use `v1.0` only
    for reproducing the preprint numbers; use `v1.2` for the
    most-recent ΔG predictions (1.3 M training measurements + extra
    residue-type embeddings).

## Reference index

- `references/installation.md` — pip flavours, vendored ColabFold /
  AlphaFold2, model + weight caches, hardware notes
- `references/cli.md` — every `bioemu.sample` flag + Python kwarg
- `references/sampling.md` — model versions, denoisers, batch sizing,
  MSA / A3M, ColabFold server overrides, output filtering, resumability
- `references/steering.md` — SMC vs FKC, the YAML schema, the
  available CVs + potentials, when to use each, how to author your own
- `references/sidechain-relax.md` — HPacker integration, OpenMM
  protocols, scaling notes
- `references/outputs.md` — file layout, frame indexing, npz schema
- `references/troubleshooting.md` — OOM, ColabFold MSA failures,
  HPacker install, monomer-only errors
- `examples/chignolin_quickstart.sh` — runnable 30-second test
- `examples/recipes.md` — common patterns (large ensemble, steering
  for long proteins, ΔG prediction, cryptic-pocket discovery, side-chain
  relax)

## Citation

> Lewis, S., Hempel, T., Jiménez-Luna, J., Gastegger, M., Xie, Y., Foong, A.Y.K.,
> Satorras, V.G., Abdin, O., Veeling, B.S., Zaporozhets, I., Chen, Y., Yang, S.,
> Foster, A.E., Schneuing, A., Nigam, J., Barbero, F., Stimper, V., Campbell, A.,
> Yim, J., Lienen, M., Shi, Y., Zheng, S., Schulz, H., Munir, U., Sordillo, R.,
> Tomioka, R., Clementi, C., Noé, F. (2025).
> *Scalable emulation of protein equilibrium ensembles with generative deep learning.*
> Science, eadv9817. https://doi.org/10.1126/science.adv9817
