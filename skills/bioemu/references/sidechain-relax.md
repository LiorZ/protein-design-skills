# Side-chain reconstruction + MD relax

BioEmu emits **backbone frames only**. To get all-heavy-atom
structures (and optionally a short MD equilibration), run the bundled
`sidechain_relax` module — a separate Typer CLI under
`src/bioemu/sidechain_relax.py`.

## What it does

```
samples.xtc (backbone) ──► HPacker (per frame, in its own venv) ──► samples_sidechain_rec.xtc (heavy atom)
                                                                                  │
                                            ┌─────────────────────────────────────┘
                                            ▼
                          OpenMM `local_minimization` OR `md_equil`  ──► samples_md_equil.xtc
```

Two stages, both opt-in:

| Stage | Run when | Output files |
|-------|----------|--------------|
| Side-chain reconstruction | always | `samples_sidechain_rec.pdb` + `samples_sidechain_rec.xtc` |
| MD equilibration | `--md-equil` (default) | `samples_md_equil.pdb` + `samples_md_equil.xtc` |
| Free MD | `--simtime-ns > 0` (requires `--md-protocol md_equil`) | `frame<N>_md_top.pdb` + per-frame trajectory |

## Install prerequisites

```bash
pip install 'bioemu[md]'           # adds openmm==8.4.0, openmm-cuda-12==8.4.0
```

Plus:
- **`conda` on PATH** (for HPacker auto-install) — or set
  `HPACKER_PYTHONBIN=/path/to/python-with-hpacker` to bypass.
- **CUDA 12 driver** (OpenMM picks up CUDA platform; falls back to
  CPU with a warning if unavailable).

## CLI

```bash
python -m bioemu.sidechain_relax \
    --pdb-path  <topology.pdb> \
    --xtc-path  <samples.xtc> \
    --outpath   <out_dir> \
    [--md-equil / --no-md-equil] \
    [--md-protocol local_minimization | md_equil] \
    [--simtime-ns <float>] \
    [--prefix <str>] \
    [--verbose]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--pdb-path` | (required) | Topology PDB. BioEmu writes one to `<output_dir>/topology.pdb`. |
| `--xtc-path` | (required) | Trajectory XTC. BioEmu writes one to `<output_dir>/samples.xtc`. |
| `--outpath` | `.` | Where outputs land. |
| `--md-equil / --no-md-equil` | `--md-equil` | If `--no-md-equil`, only run side-chain reconstruction (skip OpenMM). |
| `--md-protocol` | `local_minimization` | `local_minimization` (fast local-energy minimization only) or `md_equil` (local min → NVT 0.1 ns → NPT 0.4 ns with backbone constraint). |
| `--simtime-ns` | `0` | Additional **unconstrained** MD time in nanoseconds after the equilibration. Requires `--md-protocol md_equil`. |
| `--prefix` | `samples` | Output file prefix (`<prefix>_sidechain_rec.{pdb,xtc}`, `<prefix>_md_equil.{pdb,xtc}`). |
| `--verbose` | off | Log at DEBUG level. |

## Three usage patterns

### 1. Side chains only (fastest)

For when you just need all-heavy-atom PDB/XTC and don't care about
relax — e.g. for downstream Biotite analysis or rendering.

```bash
python -m bioemu.sidechain_relax \
    --pdb-path ~/chignolin/topology.pdb \
    --xtc-path ~/chignolin/samples.xtc \
    --outpath  ~/chignolin/relaxed \
    --no-md-equil
```

Output: `samples_sidechain_rec.{pdb,xtc}` only.

### 2. Side chains + local minimization (default — recommended)

For a clean ensemble suitable for energy-based scoring, RMSF analysis,
or visualization. Local minimization fixes clashes from side-chain
placement without changing the backbone meaningfully.

```bash
python -m bioemu.sidechain_relax \
    --pdb-path ~/chignolin/topology.pdb \
    --xtc-path ~/chignolin/samples.xtc \
    --outpath  ~/chignolin/relaxed
```

Output: both `samples_sidechain_rec.{pdb,xtc}` and
`samples_md_equil.{pdb,xtc}`.

### 3. Full MD equil (NVT + NPT + free MD)

For when you actually want short MD on each sampled conformation
(e.g. to refine clashes, or to start a longer MD per-frame).

```bash
python -m bioemu.sidechain_relax \
    --pdb-path ~/chignolin/topology.pdb \
    --xtc-path ~/chignolin/samples.xtc \
    --outpath  ~/chignolin/relaxed \
    --md-protocol md_equil \
    --simtime-ns 0.5         # 0.5 ns of free MD per frame after equilibration
```

This is **expensive** — 0.5 ns × N frames × L atoms. Run on a
subsample.

## Scaling

| Operation | Per-frame cost | Notes |
|-----------|----------------|-------|
| HPacker side-chain reconstruction | seconds to minutes | Scales linearly with L. Run on a representative subset. |
| OpenMM `local_minimization` | fast (~ seconds) | Scales linearly with system size. |
| OpenMM `md_equil` | ~ 0.1 ns NVT + 0.4 ns NPT = ~ 0.5 ns | Wall-clock depends on system + GPU. |
| Free MD (`simtime_ns`) | linear in `simtime_ns` | The big cost. |

**Run on a subsample** unless you specifically need every frame
relaxed. Easiest pattern:

```python
import mdtraj
traj = mdtraj.load_xtc("samples.xtc", top="topology.pdb")
sub = traj[::10]                    # every 10th frame
sub.save_xtc("samples_sub.xtc")
sub[0].save_pdb("topology_sub.pdb")
# then run sidechain_relax on the subset
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `RuntimeError: Error running hpacker` on first call | conda not on PATH | Install conda; or `export HPACKER_PYTHONBIN=/path/to/python-with-hpacker`. |
| `Cannot find CUDA platform` warning, but it runs | OpenMM falling back to CPU | Check `openmm-cuda-12` installed; check CUDA 12 driver. CPU works but is slow. |
| `skipping frame N due to different reconstructed topology` | HPacker produced an inconsistent topology on that frame (rare) | The frame is dropped; usually fine. Investigate if it happens to many frames in a row. |
| `Could not create MD setups for given system. Try running MD setup on reconstructed samples manually.` | Every frame failed `_prepare_system` in OpenMM | Check the topology PDB visually; non-standard residues / chain breaks can break PDBFixer. Pre-clean with `pdbfixer`. |
| Out-of-memory during OpenMM | system too large for the GPU | Run with `CUDA_VISIBLE_DEVICES=""` to force CPU; or batch the frames manually. |

## Environment variables

| Var | Default | Meaning |
|-----|---------|---------|
| `HPACKER_PYTHONBIN` | unset | Path to a Python interpreter that has `hpacker` installed. Skips auto-setup. |
| `HPACKER_VENV_DIR` | `~/.cache/bioemu/hpacker_venv/` | Where the auto-setup creates the HPacker venv. |
| `HPACKER_REPO_DIR` | `~/.cache/bioemu/hpacker/` | Where the auto-setup clones HPacker. |
