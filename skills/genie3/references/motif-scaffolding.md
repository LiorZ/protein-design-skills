# Application 2 — Motif Scaffolding

Generate a protein scaffold that holds one or more functional motifs in a
target geometry (e.g. an active site, an epitope, or a binding interface
already extracted as a substructure).

## Quick start

```bash
genie3 run -c examples/motif_scaffolding/experiment.yaml
```

Generates 5 scaffolds for MotifBench problem `22_1BCF` and evaluates them.

## Config schema

```yaml
experiment:
  name: <EXPERIMENT_NAME>

paths:
  rootdir: <OUTDIR>
  dataset: <DATADIR>          # path to a problem set directory (see below)

generation:
  dataset:
    source: motif
    selections: <CSV>         # optional: comma-separated problem names
    tags: <CSV>               # optional: comma-separated tag filter
    n_sample: <NUM_SAMPLES>   # per problem
  sampler:
    sampler:
      direction_scale: 0.1    # recommended for motif scaffolding

evaluation:
  version: scaffold
  folding:
    model_name: esmfold       # or colabfold
```

If both `selections` and `tags` are omitted, every problem in `<DATADIR>/problems/` is processed.

## Problem set on-disk layout

Provided examples:
- `data/design/motif_scaffolding/motifbench/` — 30+ single-motif MotifBench problems
- `data/design/motif_scaffolding/rsvf/`       — multi-motif RSV-F problems

Layout:

```
<DATADIR>/
  problems/
    <PROBLEM_NAME>.json
  motifs/
    <MOTIF_FILE>.pdb
```

### Motif PDB header convention

Each motif PDB starts with `REMARK 999` lines:

```
REMARK 999 NAME   <PROBLEM_NAME>
REMARK 999 INPUT  <CHAIN_ID> <START_RES> <END_RES>
REMARK 999 INPUT  <CHAIN_ID> <START_RES> <END_RES>
...
ATOM  ...
```

Each `INPUT` line defines one motif segment; the line index (1-based) is the segment ID.

### Problem JSON

```json
{
    "motif_filepaths": ["data/.../motifs/22_1BCF.pdb"],
    "segment_config_str": "8-15,A3,16-30,A4,16-30,A2,16-30,A1,8-15",
    "maximum_total_length": 125,
    "minimum_total_length": 125
}
```

- **`motif_filepaths`**: ordered list. Files are indexed `A` (first), `B` (second), `C` (third), etc.
- **`segment_config_str`**: comma-separated alternation of scaffold ranges and segment IDs.
  - Scaffold ranges: `<MIN>-<MAX>` (inclusive) flanking-residue length.
  - Segment IDs: `<MOTIF_LETTER><SEGMENT_INDEX>` — e.g. `A3` = segment 3 of motif A; `B1` = segment 1 of motif B.
- **`{minimum,maximum}_total_length`**: bounds on total scaffold length (residues).
- **(Optional) `tag`**: list of tags for `dataset.tags` filtering.

#### Single-motif example: `22_1BCF`

`segment_config_str: "8-15,A3,16-30,A4,16-30,A2,16-30,A1,8-15"`

Reads as:
1. 8–15 scaffold residues
2. Motif segment `A3` (third `INPUT` line in motif file A)
3. 16–30 scaffold residues
4. `A4`
5. 16–30 scaffold
6. `A2`
7. 16–30 scaffold
8. `A1`
9. 8–15 scaffold

#### Multi-motif example: RSVF `03_425.json`

```json
{
    "motif_filepaths": [
        "data/.../rsvf/motifs/site_iv.pdb",
        "data/.../rsvf/motifs/site_ii.pdb",
        "data/.../rsvf/motifs/site_v.pdb"
    ],
    "segment_config_str": "0-30,A1,0-30,B1,0-30,C1,0-30"
}
```

`A1`, `B1`, `C1` are the first segments of each motif file respectively.

## Generation behavior

For each requested sample, Genie 3 randomly samples a length from `[minimum_total_length, maximum_total_length]` and a scaffold-length tuple consistent with `segment_config_str`, then runs the diffusion sampler conditioned on the motif coordinates.

`direction_scale: 0.1` is the recommended default — motif scaffolding benefits from tighter conditioning than unconditional generation.

## Multi-device and multi-node

Single node, N GPUs:

```bash
genie3 run -c <CFG> --num-devices N
```

Multi-node sharding:

```bash
genie3 generate -c <CFG> --num-devices <PER_NODE> --shard-id <K> --num-shards <TOTAL>
genie3 evaluate -c <CFG> --num-devices <PER_NODE> --shard-id <K> --num-shards <TOTAL>
genie3 evaluate --reduce -c <CFG>
```

## Outputs (per problem)

`<rootdir>/<PROBLEM_NAME>/results/`:

| File | Contents |
|------|----------|
| `info.csv` | Per-design metrics: `scrmsd`, `avg_plddt`, secondary structure %, plus motif-consistency: `motif_ca_rmsd`, `motif_bb_rmsd`, `motif_aa_rmsd` |
| `successful_backbone_generation_info.csv` | `scrmsd<2 ∧ motif_ca_rmsd<2` |
| `successful_allatom_generation_info.csv` | `scrmsd<2 ∧ motif_aa_rmsd<2` |
| `successful_allatom_strict_generation_info.csv` | `scrmsd<2 ∧ motif_aa_rmsd<1` |
| `successful_{backbone,allatom,allatom_strict}_generations/` | PDBs |
| `successful_{...}_generations_cluster.csv` | FoldSeek clusters at TM 0.5/0.6/0.8 |

Multi-motif: each motif RMSD metric is the **maximum across motif segments**, so a single mis-placed segment fails the design.

### Success criteria

| Criterion | Definition |
|-----------|------------|
| **Backbone success** | `scrmsd < 2Å` AND `motif_ca_rmsd < 2Å` |
| **All-atom success** | `scrmsd < 2Å` AND `motif_aa_rmsd < 2Å` |
| **All-atom strict success** | `scrmsd < 2Å` AND `motif_aa_rmsd < 1Å` |

## Building a new motif scaffolding problem

There is no `prepare.py` for motif scaffolding (unlike binder design); you author the problem set by hand:

1. Extract the motif PDB(s) from your source structure (e.g. with `pymol`, `gemmi`, or direct ATOM-line filtering).
2. Add `REMARK 999 NAME` and `REMARK 999 INPUT` lines for each motif segment.
3. Write `<DATADIR>/problems/<PROBLEM_NAME>.json` with `motif_filepaths`, `segment_config_str`, length bounds.
4. Place the motif PDB(s) under `<DATADIR>/motifs/`.

Test with:

```bash
genie3 run -c <CFG_WITH_PATHS_DATASET=DATADIR>
```

Smoke-test on `n_sample: 5` first.

## Diagnostics

- **Failures dominated by `motif_ca_rmsd`** → the scaffold geometry isn't compatible. Try widening flanking-scaffold ranges in `segment_config_str` or increasing `n_sample`.
- **Failures dominated by `scrmsd`** → the global fold isn't sequence-recoverable. Lower `direction_scale` to `0.0` and increase `evaluation.inverse_folding.num_seq` to broaden the sequence search.
- **Multi-motif: all motif RMSDs high** → motif placements are mutually incompatible; check that segment IDs in `segment_config_str` match the motif files' `INPUT` line ordering.

## Legacy Genie 2

```bash
genie3 run -c examples/motif_scaffolding/experiment_legacy.yaml
```

Loads Genie 2 backbone-only checkpoint; otherwise identical workflow. Genie 2 only outputs Cα traces, so all-atom motif RMSD metrics are not meaningful — use backbone success instead.
