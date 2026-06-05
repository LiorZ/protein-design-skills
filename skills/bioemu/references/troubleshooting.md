# Troubleshooting

## Install / environment

| Symptom | Cause | Fix |
|---------|-------|-----|
| `pip install bioemu` fails on macOS / Windows | Linux-only | Use WSL2 on Windows; macOS not supported. |
| `jax devices: [CpuDevice]` | base install instead of `[cuda]` | `pip install 'bioemu[cuda]'`. Verify with `python -c "import jax; print(jax.devices())"`. |
| `ImportError: cannot import name 'openmm'` | did not install `[md]` | `pip install 'bioemu[md]'`. |
| `ModuleNotFoundError: bioemu.steering` | older pip resolver picked a stale version | `pip install -U bioemu`; confirm `bioemu.__version__`. |
| AF2 weight download stalls forever | flaky network to `storage.googleapis.com` | Manually `wget https://storage.googleapis.com/alphafold/alphafold_params_2022-12-06.tar` and extract to `~/.cache/colabfold/`. |
| HF checkpoint download stalls | rate limit | `export HF_HUB_DOWNLOAD_TIMEOUT=600`; or pre-download with `huggingface-cli download microsoft/bioemu`. |

## Run-time errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| `CUDA out of memory` during sampling | `batch_size_100` too high for sequence length | Halve `batch_size_100` (default 10 → try 5, 3, 1). |
| `RuntimeError: Expected all sequences to be ...` | re-running with a **different** sequence in the same `output_dir` | Use a new `output_dir`; or delete `sequence.fasta` + `batch_*.npz`. |
| `ValueError: Not sure why batch_N_M.npz already exists` | corrupted resume state | Delete the offending `batch_*.npz` and re-run. |
| `ValueError: sequence contains invalid character X` | non-canonical AA in sequence | BioEmu's `_NODE_LABEL_MAPPING` covers A/R/N/D/C/Q/E/G/H/I/L/K/M/F/P/S/T/W/Y/V plus U/O/X/B/Z. Anything else fails `check_protein_valid`. |
| Sequence is silently truncated | passed a `Path` ending in `.fasta`, but BioEmu only reads the **first** record | Make sure your FASTA is single-record, or pre-extract the sequence. |
| `samples.xtc` has fewer frames than `num_samples` | `filter_samples=True` (default) discarded unphysical samples | Expected for long / disordered sequences. Enable **physical steering** to reduce upstream; or set `filter_samples=False` to keep everything. |
| MSA step hangs forever | ColabFold public server queue | Wait, or set `msa_host_url=` to a self-hosted MMseqs2; or pre-build an A3M and pass it as `sequence=`. |
| `RuntimeError: MSA query failed` after many retries | server returned an error | Try again later; or BYO A3M; or run `colabfold_search` locally. |

## Side-chain relax errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| `RuntimeError: Error running hpacker` on first call | conda not on PATH | Install conda or `mamba`; or `export HPACKER_PYTHONBIN=/path/to/python-with-hpacker`. |
| `Cannot find CUDA platform` warning, MD super slow | `openmm-cuda-12` not installed | `pip install 'bioemu[md]'`. |
| `Could not create MD setups for given system. Try running MD setup on reconstructed samples manually.` | every frame failed in `_prepare_system` | Inspect the topology PDB; non-standard residues or chain breaks can break PDBFixer. Pre-clean with `pdbfixer --output cleaned.pdb`. |
| `skipping frame N due to different reconstructed topology` | HPacker inconsistency (rare) | The frame is dropped; usually fine. If many frames in a row → investigate the input topology. |
| Runs forever | every frame is being relaxed | Sub-sample first (`traj[::10]`), relax that. |

## Quality of the ensemble looks off

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| All samples are nearly identical | Default DPM with low N — denoiser collapsed to the AF2 mean | Switch to `heun` denoiser (`--denoiser_type heun`) for more diversity; or use a different `base_seed`. |
| Many chain breaks / clashes | Long / disordered chain, no steering | Enable physical steering (`--denoiser_config src/bioemu/config/steering/physical_steering.yaml`). |
| Ensemble doesn't show the conformational change you expect | The change is on a timescale BioEmu's training data didn't cover, or the change is multimer-only / ligand-dependent | BioEmu is monomer-only. Multimer rearrangements are out of scope. Cryptic pockets are in scope but coverage is ~55–88% — try v1.2 if v1.1 misses it; sample more. |
| `bioemu-v1.0` and `v1.1` give very similar ensembles | They share AFDB + MD training; only ΔG measurements differ | Expected. v1.2 is the one that differs more (extended MD + extra residue-type embeddings). |
| FKC RMSD-steered ensemble doesn't approach target RMSD | `num_particles` too low | Raise to 100+ (FKC default in `cv_steer.yaml`). |
| Folded fraction is way off the published number | Wrong checkpoint, or comparing to wrong reference | Use v1.1 for the Science paper numbers, v1.2 for the latest stability work. Check the [bioemu-benchmarks](https://github.com/microsoft/bioemu-benchmarks/blob/main/bioemu_benchmarks/BIOEMU_RESULTS.md) document for protocol. |

## Sanity-check snippet

```bash
# 1. Install OK?
python -c "import bioemu; print(bioemu.__version__)"
python -c "import jax; print('jax devices:', jax.devices())"
python -c "import torch; print('cuda:', torch.cuda.is_available())"

# 2. Tiny run (chignolin, ~30 s on A100)
python -m bioemu.sample \
    --sequence GYDPETGTWG --num_samples 10 \
    --output_dir /tmp/bioemu-sanity

# 3. Outputs present?
ls /tmp/bioemu-sanity
# expect: sequence.fasta  topology.pdb  samples.xtc  batch_0_*.npz

# 4. Frame count
python -c "import mdtraj; t = mdtraj.load_xtc('/tmp/bioemu-sanity/samples.xtc', \
                                              top='/tmp/bioemu-sanity/topology.pdb'); \
    print(t.n_frames, 'frames')"
```
