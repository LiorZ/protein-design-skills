# Output layout and confidence scores

## Directory layout

After `boltz predict <INPUT> --out_dir OUT`, you get:

```
OUT/
└── boltz_results_<INPUT_STEM>/
    ├── processed/
    │   ├── manifest.json
    │   ├── structures/         # tokenised inputs
    │   ├── msa/                # cached MSAs (sha256(seq).a3m)
    │   ├── constraints/        # only if YAML had constraints
    │   ├── templates/          # only if YAML had templates
    │   └── mols/               # ligand reference structures
    ├── lightning_logs/
    └── predictions/
        └── <INPUT_STEM>/
            ├── <INPUT_STEM>_model_0.cif        # candidates ordered by confidence_score
            ├── <INPUT_STEM>_model_1.cif        # (if --diffusion_samples > 1)
            ├── ...
            ├── confidence_<INPUT_STEM>_model_0.json
            ├── confidence_<INPUT_STEM>_model_1.json
            ├── ...
            ├── plddt_<INPUT_STEM>_model_0.npz
            ├── pae_<INPUT_STEM>_model_0.npz    # only with --write_full_pae
            ├── pde_<INPUT_STEM>_model_0.npz    # only with --write_full_pde
            ├── embeddings_<INPUT_STEM>_model_0.npz  # only with --write_embeddings
            └── affinity_<INPUT_STEM>.json      # only if properties.affinity was set
```

If you predicted a directory of YAMLs, every input gets its own subfolder under `predictions/`.

- `<INPUT_STEM>` is the YAML / FASTA filename without extension.
- `_model_0.cif` is the **best-ranked** structure (highest `confidence_score`).
- File format respects `--output_format`: default mmCIF (`.cif`), or `.pdb` if passed.

## The structure file (`.cif` / `.pdb`)

- Chains are labelled with the `id:` fields from the YAML.
- The per-token pLDDT score is written into the B-factor column of the structure (0–100 scale).
- For mmCIF, additional pLDDT and chain-mapping metadata are written under standard mmCIF categories.

To recover atoms / chains in Python:

```python
import gemmi
structure = gemmi.read_structure("predictions/<stem>/<stem>_model_0.cif")
for model in structure:
    for chain in model:
        for residue in chain:
            for atom in residue:
                ...  # atom.b_iso is the pLDDT
```

Biopython works as well (`Bio.PDB.MMCIFParser`).

## `confidence_*.json` — per-sample summary scores

One file per diffusion sample. All scores in `[0, 1]` unless noted, with **higher = more confident** (except `pde` / `ipde`, which are Å — lower is better).

```jsonc
{
  "confidence_score": 0.8367,    // 0.8 * complex_plddt + 0.2 * iptm  (ptm for single chains)
  "ptm":            0.8425,      // pTM for the whole complex
  "iptm":           0.8225,      // interface-restricted pTM (multimers only; 0 for monomers)
  "ligand_iptm":    0.0,         // ipTM restricted to protein-ligand interfaces
  "protein_iptm":   0.8225,      // ipTM restricted to protein-protein interfaces
  "complex_plddt":  0.8402,      // mean pLDDT across all tokens
  "complex_iplddt": 0.8241,      // mean pLDDT at interface residues (upweighted)
  "complex_pde":    0.8912,      // mean PDE across all token pairs (Å, lower = better)
  "complex_ipde":   5.1650,      // mean PDE at interface pairs (Å)
  "chains_ptm": {                // per-chain pTM
    "0": 0.8533,
    "1": 0.8330
  },
  "pair_chains_iptm": {          // chain-pair ipTM matrix (chain index → chain index)
    "0": { "0": 0.8533, "1": 0.8090 },
    "1": { "0": 0.8225, "1": 0.8330 }
  }
}
```

### Practical thresholds

| Metric | Field | Meaning |
|--------|-------|---------|
| Overall confidence | `confidence_score` | > 0.8 = high; 0.6–0.8 = OK; < 0.6 = suspicious. |
| Monomer fold | `ptm`, `complex_plddt` | `ptm > 0.5`, `plddt > 70` → real fold. |
| Multimer interface | `iptm` | > 0.75 = strong; 0.5–0.75 = ambiguous; < 0.5 = likely no interaction. |
| Protein-ligand contact | `ligand_iptm` | > 0.6 = decent; below that often means the ligand is on the surface, not in a pocket. |
| Local quality at interface | `complex_iplddt` | > 70 = ordered; < 50 = disordered or wrong. |

For **binder ranking** (designed binder vs target):

- `iptm` overconfidences binders systematically; use ipSAE instead (see the `ipsae` skill) or combine `iptm` with `ligand_iptm`, `complex_iplddt`, and a clash check.
- Cross-validate with multiple seeds / `--diffusion_samples > 1`.

## `plddt_*_model_K.npz`

NPZ with one array `plddt` of shape `(num_tokens,)`, values in `[0, 100]`. Tokens are atoms for ligands and residues for polymers, in the order they appear in the structure.

```python
import numpy as np
plddt = np.load("plddt_<stem>_model_0.npz")["plddt"]   # (T,)
```

## `pae_*_model_K.npz` (only with `--write_full_pae`)

Predicted aligned error in Å. Shape `(num_tokens, num_tokens)`, asymmetric.

```python
pae = np.load("pae_<stem>_model_0.npz")["pae"]   # (T, T)
```

Use this for:

- Cropping rigid domains (low PAE blocks).
- Estimating interface confidence at specific token pairs.
- Computing ipSAE (see `ipsae` skill).

## `pde_*_model_K.npz` (only with `--write_full_pde`)

Predicted distance error in Å. Same shape as PAE.

## `embeddings_*_model_K.npz` (only with `--write_embeddings`)

Single (`s`) and pair (`z`) embeddings exported as NPZ. Use for downstream learning (binder filtering, regressors). Shapes:

- `s`: `(num_tokens, d_single)`
- `z`: `(num_tokens, num_tokens, d_pair)`

Dimensions depend on `--model` (Boltz-1 vs Boltz-2 differ).

## `affinity_*.json` (only with `properties.affinity`)

```json
{
  "affinity_pred_value": -1.23,         // log10(IC50_uM); lower = stronger binder
  "affinity_probability_binary": 0.87,  // probability of binding
  "affinity_pred_value1": -1.18,
  "affinity_probability_binary1": 0.85,
  "affinity_pred_value2": -1.27,
  "affinity_probability_binary2": 0.89
}
```

See [affinity.md](affinity.md) for interpretation.

## Ranking samples

Boltz writes `_model_K.cif` files ordered by `confidence_score` *descending*, so `model_0` is the top pick. Re-rank if you have a domain-specific metric:

```python
from pathlib import Path
import json

base = Path("predictions/example")
ranked = sorted(
    base.glob("confidence_example_model_*.json"),
    key=lambda p: -json.loads(p.read_text())["confidence_score"],
)
top = ranked[0].with_suffix(".cif")  # the corresponding CIF
```

For multimers and binders, prefer ranking by `iptm` or (better) ipSAE.

## Cleaning up

The `processed/` and `lightning_logs/` folders are reusable across runs sharing the same `--out_dir`. They are safe to delete after a campaign finishes — only `predictions/` contains user-facing data.
