# Binding affinity prediction (Boltz-2 only)

Boltz-2 adds a dedicated affinity head that runs after structure prediction. It produces **two** numbers per affinity-requested ligand, trained on different supervisions and meant for different stages of a drug-discovery campaign.

## How to request affinity

In your YAML:

```yaml
version: 1
sequences:
  - protein:
      id: A
      sequence: MVTPEGNVSLVDESLLVGV...
      msa: ./examples/msa/seq1.a3m
  - ligand:
      id: B
      smiles: 'N[C@@H](Cc1ccc(O)cc1)C(=O)O'
properties:
  - affinity:
      binder: B               # ligand chain id; must be a single string, not a list
```

Run as usual:

```bash
boltz predict affinity.yaml --use_msa_server
```

CLI knobs specific to affinity:

| Flag | Default | Purpose |
|------|---------|---------|
| `--sampling_steps_affinity N` | 200 | Diffusion steps for the affinity head. |
| `--diffusion_samples_affinity N` | 5 | How many affinity samples to average. |
| `--affinity_mw_correction` | False | Apply molecular-weight correction. |
| `--affinity_checkpoint PATH` | None | Custom affinity checkpoint. |

## Hard constraints

- **Boltz-2 only**: `--model boltz2` (the default). Boltz-1 has no affinity head.
- Exactly **one** affinity ligand per YAML.
- `binder` must be a `ligand` entry. SMILES or CCD both work.
- Ligand **size**:
  - Hard cap **128 heavy atoms** (after `RDKit.Chem.RemoveHs`). Above this, the parser raises.
  - Training cap was **56**. Between 56 and 128 you get a runtime `WARNING` and the affinity number is unreliable.
- Target type: trained on **protein** targets only. The model still runs against DNA / RNA / cofactor "targets" but the output is meaningless — don't use it.
- One ligand copy: `id: [B, C]` with multiple copies and affinity raises (`Cannot compute affinity for a ligand that has multiple copies!`).
- One residue ligands: multi-residue ligand records (rare with CCDs) also raise (`Cannot compute affinity for multi residue ligands!`).

## Output: `affinity_<input_stem>.json`

```json
{
  "affinity_pred_value": -1.23,
  "affinity_probability_binary": 0.87,
  "affinity_pred_value1": -1.18,
  "affinity_probability_binary1": 0.85,
  "affinity_pred_value2": -1.27,
  "affinity_probability_binary2": 0.89
}
```

The ensemble is two models; `_value` / `_probability_binary` are the ensemble (recommended), `_value1` / `_value2` are the individual model outputs.

### `affinity_probability_binary` — for hit-finding

- Range `[0, 1]`.
- "Predicted probability that this ligand is a binder vs a decoy."
- **Use case**: rank a screening library, separate binders from non-binders.
- Higher = more likely to bind.
- Threshold rule of thumb: > 0.5 = candidate hit; > 0.7 = strong signal. Calibrate per target.

### `affinity_pred_value` — for lead optimization

- Output is `log10(IC50_µM)` — i.e. the model's predicted IC50 expressed in micromolar, then `log10`.
- **Lower = stronger binder.**
  - Output `−3` ↔ IC50 ≈ 10⁻³ µM = **1 nM** (strong binder).
  - Output `0`  ↔ IC50 ≈ 1 µM (moderate).
  - Output `+2` ↔ IC50 ≈ 100 µM (very weak / decoy).
- Trained on actives — only compare among ligands you already believe are active. Do **not** use it as a binder-vs-decoy classifier; that's what `affinity_probability_binary` is for.
- Convert to pIC50 in kcal/mol: `pIC50_kcal_per_mol = (6 - affinity_pred_value) * 1.364`.
  - e.g. output `-2` → `(6 - (-2)) * 1.364 = 10.91` kcal/mol pIC50.

### When to use each

| Stage | Use |
|-------|-----|
| Virtual screening (filter ~10⁶ → ~10⁴) | `affinity_probability_binary` only |
| Hit triage (~10⁴ → ~10²) | `affinity_probability_binary` + structural confidence (pLDDT, ipTM, clashes) |
| Hit-to-lead / lead-opt (R-group changes) | `affinity_pred_value` between active analogs |
| Absolute binding number for a single compound | Don't — Boltz-2 is calibrated *relatively* well, but absolute IC50 has wide error bars |

## `--affinity_mw_correction`

This flag enables an additive correction that compensates for the fact that the value head can be biased by ligand size. It is most useful when you compare ligands with very different molecular weights (e.g. fragments vs lead molecules). In a homogeneous SAR series with similar MWs, the correction has little effect. The Boltz-2 paper reports the correction as off by default but useful on cross-chemotype benchmarks.

## Runtime cost

Affinity adds one extra diffusion pass per `--diffusion_samples_affinity` samples (default 5). Wall-time roughly doubles compared to structure-only prediction. To skip affinity, simply omit the `properties:` block.

## Practical recipe — screening a ligand library

For each candidate ligand `L_i`:

1. Build a YAML with `protein` (target) + `ligand` (one of `L_i`) + `properties.affinity.binder: <ligand_id>`.
2. Place all per-ligand YAMLs in a directory.
3. `boltz predict library_dir/ --use_msa_server --devices N` to shard across GPUs.
4. Aggregate by reading every `boltz_results_*/predictions/*/affinity_*.json`.
5. Rank ligands by `affinity_probability_binary` (descending). Cross-filter with structural confidence: drop entries where `confidence_score < 0.5` or `has_inter_chain_clashes` from `confidence_*.json`.

Tip: you don't need to re-fetch the MSA for every ligand — predict the target MSA once with `--use_msa_server`, copy the cached `.a3m` from `processed/msa/<sha256>.a3m` into a stable location, and reference it in every YAML's `msa:` field. That avoids hammering the ColabFold server.

## Validation against FEP / experimental data

The Boltz-2 paper benchmarks affinity against:

- The FEP+ benchmark (Schrödinger).
- CASP16 affinity track.
- MF-PCBA (internal MIT test set).

It approaches FEP-level Pearson correlation on FEP+ at ~1000x lower compute. Numbers and exact comparison code are released alongside the paper (see [evaluation reference](https://github.com/jwohlwend/boltz/blob/main/docs/evaluation.md)).

For your own validation:

- Use `affinity_probability_binary` against a labelled binder/non-binder set; report AUC / EF₁%.
- Use `affinity_pred_value` against an SAR set with measured IC50s of analogs; report Pearson / Spearman R after converting Boltz output to log(IC50_µM) (no extra transform needed — it is already log(IC50_µM)).
