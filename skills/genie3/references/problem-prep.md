# Building a New Binder Design Problem Set

`scripts/problem/binder_design/prepare.py` turns a configuration YAML +
target PDBs into a Genie-3-compatible problem set (problem JSONs + FASTA +
MSAs + reformatted PDBs). The example shipped with the repo is
`scripts/problem/binder_design/binderbench/`.

For motif scaffolding, there is no `prepare.py` — author the problem set
by hand. See [motif-scaffolding.md#building-a-new-motif-scaffolding-problem](motif-scaffolding.md#building-a-new-motif-scaffolding-problem).

## Workflow

```bash
conda activate genie3

python scripts/problem/binder_design/prepare.py \
    --config <CONFIG_FILEPATH> \
    --outdir <OUTPUT_DIRECTORY>

# Then point an experiment YAML at it:
#   paths:
#     dataset: <OUTPUT_DIRECTORY>/<config.name>
```

## Input config YAML

```yaml
name: my_problem_set        # appears as the subdirectory name under <outdir>
problem:

  01_target_a:              # problem key (used in selections, in info.csv)
    name: TargetA           # human-readable display name
    target:
      filepath: path/to/target.pdb
      hotspot:               # whitespace-separated tags (chain + residue index)
        A65
        A74
        A93
      sequence:              # OPTIONAL: full target sequence(s), one per chain (whitespace-separated)
        MAEK...
        MGSS...
      common:                # OPTIONAL: user-provided common interface (cond_strategy: common)
        A60
        A65
        A70
    binder:
      min_length: 80
      max_length: 120
    tag:                     # OPTIONAL: tags for dataset.tags filtering
      AlphaProteo
    other:                   # OPTIONAL: extra metadata copied verbatim into JSON
      pdb_id: 2WH6

  02_target_b:
    name: TargetB
    ...
```

## What `prepare.py` does

For each problem (uses `ml_collections.ConfigDict` to navigate the config):

1. **Validates the target PDB**:
   - No insertion codes (`line[26]`) and no alternative locations (`line[16]`) → exits if found.
   - Every hotspot tag (e.g. `A65`) must match a CA atom in the PDB → exits with the missing list otherwise.
2. **Parses chains** with `parse_pdb` (`src/genie3/generation/utils/pdb_utils.py`):
   - Each chain's sequence is reconstructed from CA residues with `'-'` placeholders for missing residues.
   - If `sequence` is provided in the config, aligns the PDB-derived sequence to the full sequence to recover the residue-index offset (handles N-terminal disorder).
   - Reassigns chain IDs starting from `B` (so the future binder chain is `A`).
3. **Writes FASTA**:
   - `targets/fasta/<key>.fasta` — colon-joined multi-chain FASTA
   - `targets/fasta/<key>-chain_<X>.fasta` — per-chain FASTAs
4. **Writes reformatted PDB**:
   - `targets/pdb/<key>.pdb` with `REMARK 999 KEY/NAME/TARGET` header + renumbered chains/residues
   - `targets/pdb/<key>-chain_<X>.pdb` per chain
5. **Generates MSAs** by calling `colabfold_batch <fasta> <tmp_outdir> --msa-only`:
   - `targets/msa/<key>.a3m` (full complex)
   - `targets/msa/<key>-chain_<X>.a3m` per chain
   - Requires internet — uses ColabFold's MMseqs2 server. Runs sequentially per problem.
6. **Computes interface residues**:
   - `target_interface_residues.hotspot` — re-tagged hotspots
   - `target_interface_residues.extended` — `compute_extended_interface(...)` on the target PDB around the hotspots (Cα distance threshold based, `version_num=1`)
   - `target_interface_residues.common` — copied from config if provided, else absent
7. **Writes problem JSON** to `<outdir>/<config.name>/problems/<key>.json`.

## Output layout

```
<outdir>/<config.name>/
  problems/
    01_target_a.json
    02_target_b.json
  targets/
    pdb/
      01_target_a.pdb
      01_target_a-chain_B.pdb
      02_target_b.pdb
      ...
    fasta/
      01_target_a.fasta
      01_target_a-chain_B.fasta
      ...
    msa/
      01_target_a.a3m
      01_target_a-chain_B.a3m
      ...
```

## Problem JSON schema

```json
{
    "key": "01_target_a",
    "name": "TargetA",
    "target_pdb_filepath": "<outdir>/<config.name>/targets/pdb/01_target_a.pdb",
    "target_fasta_filepath": "<outdir>/<config.name>/targets/fasta/01_target_a.fasta",
    "target_msa_filepath": "<outdir>/<config.name>/targets/msa/01_target_a.a3m",
    "target_pdb_filepath_by_chain": ["..."],
    "target_fasta_filepath_by_chain": ["..."],
    "target_msa_filepath_by_chain": ["..."],
    "target_chain_and_residues": ["B1-157"],
    "target_interface_residues": {
        "hotspot":  ["B65", "B74", "B93"],
        "extended": ["B60","B61",...,"B102"],
        "common":   ["B60","B65","B70"]   // only if provided in config
    },
    "binder_min_length": 80,
    "binder_max_length": 120,
    "tag": ["AlphaProteo"],
    "pdb_id": "2WH6"           // from "other"
}
```

## Running with the new problem set

```yaml
experiment: { name: my_run }
paths:
  rootdir: out/my_run
  dataset: <outdir>/my_problem_set     # the directory containing problems/ and targets/

generation:
  dataset:
    source: target
    selections: 01_target_a
    n_sample: 100
  sampler:
    sampler:
      direction_scale: 0.0

evaluation:
  version: binder
  inverse_folding: { num_seq: 1 }
  folding:
    model_name: colabfold
    mode: template
```

## Hard constraints / gotchas

- **`outdir` must not already exist** — prepare.py exits if `<outdir>/<config.name>` is present. Either pick a fresh name or delete the directory first.
- **No insertion codes / altlocs** — clean the PDB first (e.g. `pdb_selaltloc`, `gemmi`).
- **Hotspot tags must match exactly** — chain ID + residue index from the *original* PDB. The script remaps to its renumbered tags after alignment.
- **MSA generation requires internet** — `colabfold_batch --msa-only` queries the public MMseqs2 server. For airgapped runs, prepare MSAs separately and place them in the expected paths before running.
- **First future chain in the binder PDB is `A`** — the `prepare.py` script renumbers target chains starting from `B` so the binder slot is `A`. The binder reducer assumes this.
- **`other` keys** are merged into the top level of the problem JSON. They cannot collide with any existing key (the script exits on conflict).

## Programmatic usage

`prepare.process(problem, outdir)` is callable from Python; pass a `ConfigDict` problem entry plus the output directory. Useful for batching many problems with custom logic.
