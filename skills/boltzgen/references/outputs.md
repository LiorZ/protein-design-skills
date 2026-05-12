# Output directory layout

A completed `boltzgen run --output OUT/ …` produces:

```
OUT/
├── config/                                # resolved Hydra configs for each step
│   ├── design.yaml
│   ├── inverse_folding.yaml
│   ├── folding.yaml
│   ├── design_folding.yaml                # if applicable
│   ├── affinity.yaml                      # if applicable
│   ├── analysis.yaml
│   └── filtering.yaml
├── steps.yaml                             # manifest of enabled steps
│
├── intermediate_designs/                  # output of the design step
│   ├── <design_id>.cif                    # backbone-only structure
│   ├── <design_id>.npz                    # metadata (chain IDs, masks, …)
│   └── …
│
├── intermediate_designs_inverse_folded/   # output of IF / folding / design_folding / affinity
│   ├── <design_id>.cif                    # IF'd structure (designed sidechains 0,0,0)
│   ├── <design_id>.npz
│   ├── refold_cif/
│   │   └── <design_id>.cif                # Boltz-2 refold of (target + binder)
│   ├── refold_design_cif/                 # only if design_folding ran
│   │   └── <design_id>.cif                # Boltz-2 refold of binder alone
│   ├── affinity_<design_id>.json          # only if affinity ran (Boltz-2 affinity head)
│   ├── aggregate_metrics_analyze.csv      # analysis output (one row per design)
│   └── per_target_metrics_analyze.csv     # analysis output (one row per target)
│
└── final_ranked_designs/                  # output of the filtering step
    ├── intermediate_ranked_<N>_designs/   # top-N by quality only (no diversity step)
    │   └── <design_id>.cif                # copied from refold_cif/
    ├── final_<budget>_designs/            # quality + diversity selected set
    │   └── <design_id>.cif                # copied from refold_cif/
    ├── all_designs_metrics.csv            # metrics for every design considered
    ├── final_designs_metrics_<budget>.csv # metrics for the selected set only
    └── results_overview.pdf               # summary plots
```

## File-by-file

### `config/<step>.yaml`

The resolved Hydra config that was used for each step. Useful for:

- Reproducibility: copy this directory and run `boltzgen execute OUT/`
  to re-run with the exact same configs.
- Debugging: confirms what `--config`, `--protocol`, and protocol-default
  overrides actually composed to.

### `steps.yaml`

Top-level manifest listing the enabled steps and their config paths.

```yaml
steps:
  - name: design
    config_path: config/design.yaml
  - name: inverse_folding
    config_path: config/inverse_folding.yaml
  …
```

### `intermediate_designs/<design_id>.cif`

Backbone-only mmCIF from the diffusion step. The "sequence" present
here is the diffusion-time best guess and is replaced by inverse folding
in the next step. Useful for diagnosing diffusion-time issues, but
**not** the file you ship.

### `intermediate_designs_inverse_folded/<design_id>.cif`

After inverse folding. Has both target and binder; **designed residues
have backbone atoms only**, with sidechain coordinates set to (0, 0, 0)
as a sentinel — the sequence is correct, but sidechain placement is
done by the subsequent folding step.

### `refold_cif/<design_id>.cif`

After Boltz-2 refolding of (target + binder). **This is the primary
structure file you'll inspect, score, or share.** Sidechains are
correctly placed.

### `refold_design_cif/<design_id>.cif`

After `design_folding` (the binder refolded *without* the target). Only
present under `protein-anything`, `protein-small_molecule`,
`protein-redesign`. Useful for checking that the binder folds on its
own — diverged behavior between this and `refold_cif/` is a red flag.

### `affinity_<design_id>.json`

Boltz-2 affinity-head outputs:

```json
{
  "affinity_pred_value": -0.83,        // log10(IC50 µM), lower = stronger
  "affinity_probability_binary": 0.72  // probability it binds at all
}
```

Caveats:

- Ligands > 56 heavy atoms produce a `WARNING` and unreliable values.
- Ligands > 128 heavy atoms are rejected.
- Only protein × small-molecule pairs are valid — affinity numbers on
  protein / DNA / RNA targets are nonsense.

### `aggregate_metrics_analyze.csv`

One row per design, with all the analysis-step metric columns —
`iptm`, `refolding_rmsd`, `plip_hbonds_refolded`, `delta_sasa_refolded`,
liabilities, `design_ALA` / `design_GLY` / … composition fractions, etc.
See [`filtering.md`](filtering.md) for the column list.

### `final_<budget>_designs/`

The shipped set. CIFs are *copies* of files from `refold_cif/`, so they
have the binder + target with sidechains. The filenames retain the
design ID for traceability.

### `final_designs_metrics_<budget>.csv`

Same columns as `all_designs_metrics.csv` but filtered to the chosen
set. Sort by `rank` to recover the ordering.

### `results_overview.pdf`

The auto-generated campaign report. See `filtering.md` § "Reading
results_overview.pdf" for what's in it.

## Inspecting outputs

### Count surviving designs

```bash
ls OUT/final_ranked_designs/final_*_designs/*.cif | wc -l
```

### Top-1 by composite rank

```bash
python -c "
import pandas as pd
df = pd.read_csv('OUT/final_ranked_designs/final_designs_metrics_30.csv')
print(df.sort_values('rank').iloc[0][['design_id','iptm','refolding_rmsd','plip_hbonds_refolded']])
"
```

### Convert a CIF to PDB

```python
from Bio.PDB import MMCIFParser, PDBIO
parser = MMCIFParser(QUIET=True)
s = parser.get_structure('design', 'OUT/final_ranked_designs/final_30_designs/d0.cif')
PDBIO().set_structure(s)
PDBIO().save('d0.pdb')
```

Or with `gemmi`:

```bash
gemmi convert d0.cif d0.pdb
```

### Visualize the binding site as defined in the YAML

```bash
boltzgen check spec.yaml --output check_out/
# then open check_out/spec.cif in https://molstar.org/viewer/
```

The colored CIF shows binding residues, structure-groups, and design
masks distinctly.

## Things you might expect that aren't here

- **No FASTA** is written by default. To get sequences, parse the
  `_atom_site` records of the IF'd / refolded CIFs, or read them from
  `aggregate_metrics_analyze.csv` (column `design_sequence`).
- **No PAE NPZ** unless you turn on the corresponding `analysis` toggle.
  (Boltz-2 stand-alone does emit them — pipe the final binders through
  the `boltz` skill if you want NPZ artifacts.)
- **No MSA files** — BoltzGen does not use ColabFold MMseqs2 during the
  pipeline. (The target features are built from the input CIF directly.)
- **No `lightning_logs/`** by default — subprocess execution suppresses
  Lightning's per-step logger directory in favor of stdout.
