# Validating designed binders with Boltz

Boltz is one of the standard cross-validation tools for protein-binder design campaigns. It is often used to re-score outputs from RFdiffusion, BindCraft, BoltzGen, or Genie3 to estimate which designs are worth experimentally testing.

## Workflow

1. **Generate designs** with your design tool (`rfdiffusion`, `bindcraft`, `boltzgen`, `genie3`).
2. **Build a YAML per design** with the target + the designed binder.
3. **Predict with Boltz**, ideally with multiple diffusion samples and a fixed seed for reproducibility.
4. **Rank** by a combination of `iptm`, ipSAE, interface pLDDT, and clash flags.
5. **Order the top N** for experimental testing.

## Minimal binder-validation YAML

```yaml
version: 1
sequences:
  - protein:
      id: A                   # target
      sequence: <TARGET_SEQ>
      msa: ./msa_target.a3m
  - protein:
      id: B                   # designed binder
      sequence: <BINDER_SEQ>
      msa: empty              # designed sequences have no natural MSA
```

Notes:

- For the **target**, use a real MSA (server or local `.a3m`) — this anchors the target fold.
- For the **binder**, use `msa: empty` (single-sequence). De novo designed sequences have no homologs; an auto-MSA on the binder degrades accuracy because hits will be irrelevant noise.
- Use `--use_msa_server` only if the binder is naturally derived (e.g. a known scaffold). For de novo binders, the auto-MSA is harmful.

## With a pocket hint

If the design was conditioned on hotspot residues on the target, pass them as a `pocket` constraint to keep Boltz consistent with the design intent:

```yaml
constraints:
  - pocket:
      binder: B
      contacts:
        - [A, 138]
        - [A, 142]
      max_distance: 6
```

Don't `force: true` — you want Boltz's independent assessment of whether the design lands on the pocket.

## Recommended `predict` invocation

```bash
boltz predict design_yamls/ \
  --out_dir boltz_validation/ \
  --diffusion_samples 5 \
  --recycling_steps 3 \
  --seed 42 \
  --devices 4 \
  --use_msa_server
```

- `--diffusion_samples 5`: gives variance to spot unstable designs (good designs are consistent across samples).
- `--seed 42`: reproducible ranking.
- `--devices 4`: shard a directory of YAMLs across 4 GPUs (DDP).

For a **fast triage pass** of thousands of designs, drop to `--diffusion_samples 1 --recycling_steps 1` and re-score only the top fraction with the full settings.

## Ranking metrics

Aggregate the per-design `confidence_*.json` files:

```python
import json
from pathlib import Path

rows = []
for cdir in Path("boltz_validation").glob("boltz_results_*"):
    for cfg in cdir.glob("predictions/*/confidence_*_model_0.json"):
        d = json.loads(cfg.read_text())
        rows.append({
            "design": cfg.parent.name,
            "iptm": d["iptm"],
            "ptm": d["ptm"],
            "iplddt": d["complex_iplddt"],
            "plddt": d["complex_plddt"],
            "pair_iptm_A_B": d["pair_chains_iptm"]["0"]["1"],
        })
```

### Don't rank by ipTM alone

`iptm` consistently overconfidences designed binders — many designs score 0.8+ on ipTM but fail experimentally. Use **ipSAE** (see the `ipsae` skill) on the resulting CIFs / PAE files for substantially better correlation with experimental success rates.

Practical heuristic for a *first-pass* cutoff (filter, not rank):

| Metric | Filter |
|--------|--------|
| `iptm`            | > 0.6  |
| `complex_iplddt`  | > 60   |
| pair-chain ipTM (binder ↔ target) | > 0.5 |
| `has_inter_chain_clashes` (from `confidence_*_model_0.json` if present) | False |

Then rank the survivors by ipSAE.

## Multiple seeds for stability

A single Boltz prediction is one sample of the model's posterior. For binder validation, **run multiple seeds** and report the median / worst metric:

```bash
for SEED in 1 2 3 4 5; do
  boltz predict design.yaml --out_dir runs/seed_${SEED}/ \
    --diffusion_samples 1 --seed $SEED --use_msa_server
done
```

A "robust" binder is one where ipSAE and ipTM are stable across seeds; a "lucky" design has high ipTM in one seed and collapses in another.

## With affinity (Boltz-2)

For small-molecule designs (PROTACs, fragments, macrocycles encoded as CCD), you can layer affinity prediction on top:

```yaml
sequences:
  - protein: { id: A, sequence: ..., msa: ./msa_A.a3m }
  - ligand:  { id: L, smiles: ... }
properties:
  - affinity:
      binder: L
```

Use `affinity_probability_binary` to filter binders vs decoys, then `affinity_pred_value` (Δ between analogs) to rank.

## Common pitfalls

- **Auto-MSA on a designed sequence** — produces noise hits; explicitly set `msa: empty` for de novo binders.
- **Single sample ranking** — many designs are within noise of each other at `--diffusion_samples 1`. Use 3–5 samples for ranking, more for borderline calls.
- **Comparing across MSAs** — different MSA depths shift ipTM by 5–10%. Keep the target MSA fixed when comparing binders.
- **Symmetric chain handling** — if the target is a homodimer, declare both copies with `id: [A, B]` so the binder is scored against the whole interface, not just half of it.
- **Trusting absolute ipTM** — calibrate against in-house experimental data first. Boltz ipTM is well-correlated with success *rank* but the absolute number is design-tool-specific.

## Cross-references

- `ipsae` skill — better ranking score than ipTM, drop-in over Boltz outputs.
- `protein-qc` skill — QC thresholds (pLDDT, ipTM, PAE) backed by competition data.
- `binder-design` skill — tool selection for the *design* step.
- `bindcraft` / `rfdiffusion` / `boltzgen` / `genie3` — design tools whose outputs you validate here.
- `chai-lab` / `alphafold` skills — alternative structure predictors; running >=2 in agreement increases confidence further.
