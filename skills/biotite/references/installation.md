# Installing Biotite

Biotite is a normal Python package — **no GPU, no container, no model
weights**. It ships compiled extensions (Cython/Rust) as wheels on PyPI and
conda-forge.

## Core install

```bash
pip install biotite
# or
conda install -c conda-forge biotite
# or, fast resolver:
mamba install -c conda-forge biotite
```

- **Python ≥ 3.11** required.
- Hard dependencies (pulled automatically, all lightweight):
  `numpy ≥ 1.25`, `requests ≥ 2.12`, `msgpack ≥ 0.5.6`, `networkx ≥ 2.0`.
- Wheels are built against NumPy 2.0 but are backward compatible with NumPy 1.x.

Verify:

```python
import biotite
print(biotite.__version__)        # e.g. 1.6.0
```

## From source (development version)

```bash
git clone https://github.com/biotite-dev/biotite.git
cd biotite
pip install .            # builds the Cython + Rust extensions (needs a compiler + Rust toolchain)
```

The local checkout at `~/Repos/biotite` is past the `v1.6.0` tag (next-release
development). For reproducible work, pin a release (`pip install biotite==1.6.0`).

## Optional dependencies — only what you use

Biotite's core is self-contained. Two subpackages reach outside it.

### `biotite.interface` — conversion bridges

Each bridge imports an external Python package; install the one you need:

| Bridge | Install | Note |
|--------|---------|------|
| `biotite.interface.rdkit` | `pip install rdkit` (or `conda install -c conda-forge rdkit`) | needs **RDKit ≥ 2024.09.1** for `to_mol`/`from_mol` |
| `biotite.interface.openmm` | `conda install -c conda-forge openmm` | `to_system` / `to_topology` / `from_state(s)` |
| `biotite.interface.pymol` | open-source PyMOL in the same env (`conda install -c conda-forge pymol-open-source`) | library-mode rendering via `launch_pymol()` |

### `biotite.application` — external command-line tools

These wrappers **shell out to a binary that you must install separately** and
have on `PATH`. Biotite only builds the command line and parses the output.

| Wrapper (class) | Binary | Install hint |
|-----------------|--------|--------------|
| `DsspApp` | `mkdssp` | `conda install -c salilab dssp` or `conda install -c conda-forge dssp` |
| `MuscleApp` / `Muscle5App` | `muscle` | `conda install -c bioconda muscle` |
| `MafftApp` | `mafft` | `conda install -c bioconda mafft` |
| `ClustalOmegaApp` | `clustalo` | `conda install -c bioconda clustalo` |
| `VinaApp` | `vina` | AutoDock Vina (`conda install -c bioconda autodock-vina`) |
| `RNAfoldApp` / `RNAplotApp` | `RNAfold` / `RNAplot` | ViennaRNA (`conda install -c bioconda viennarna`) |
| `TantanApp` | `tantan` | `conda install -c bioconda tantan` |
| `FastqDumpApp` | `prefetch` + `fasterq-dump` | NCBI SRA-Tools (`conda install -c bioconda sra-tools`) |

**Web apps need no binary** — they hit a remote service over HTTP:
- `BlastWebApp` → NCBI BLAST URL API (be polite; it rate-limits and asks for a
  contact e-mail).

The `biotite.database` subpackage (RCSB / Entrez / UniProt / AFDB / PubChem)
also needs no binary — it is pure `requests` against public REST APIs. An NCBI
**API key** raises Entrez rate limits (`biotite.database.entrez.set_api_key`);
see `database.md`.

## A clean working env

```bash
conda create -n biotite python=3.12 -c conda-forge \
    biotite rdkit openmm pymol-open-source \
    mafft muscle clustalo dssp viennarna
conda activate biotite
```

That covers the library plus the most common interface/application
dependencies. Drop whatever you do not need.
