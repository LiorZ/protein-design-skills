# Validating designed binders with Chai-1

Chai-1 is widely used as a **validator** for binders produced by
backbone-generation tools (RFdiffusion, BindCraft, BoltzGen, Genie 3)
and sequence-design tools (ProteinMPNN, LigandMPNN, SolubleMPNN). This
guide is how to wire it in.

## The basic recipe

1. **Build a two-chain FASTA** with binder chain first, then target.
2. **Fold without MSAs** (designed binder = no MSA signal; target MSA
   often unnecessary and slow at scale).
3. **Pull `iptm`, per-chain-pair ipTM, interface pLDDT, and the clash
   flag** out of the scores npz.
4. **Combine into a composite ranking** — `iptm` alone is not enough
   (see below).
5. **Filter, then experimentally test the top survivors.**

```bash
chai-lab fold designs/design_042.fasta out/design_042/ \
              --num-diffn-samples 5 \
              --fasta-names-as-cif-chains \
              --seed 0
```

…where `design_042.fasta` is:

```
>protein|name=B
GSDESIGN... (binder)
>protein|name=T
MASIYR... (target)
```

## Why not just look at ipTM

ipTM (and Chai's `aggregate_score`) is the de-facto metric people start
with for binder validation. But on designed binders specifically, ipTM
**systematically overconfidences** false positives — many binders score
0.7–0.8 ipTM but fail experimentally.

Better options on Chai outputs:

| Metric | Tool | Why |
|--------|------|-----|
| **ipSAE** | `ipsae` skill | Trained-and-validated as a binder-success predictor; uses Chai's PAE + CIF directly. Substantially better than ipTM. |
| **Interface pLDDT** | compute yourself | Mean per-token pLDDT for binder residues within ~5 Å of target. Cheap, effective. |
| **Per-chain-pair ipTM[B,T]** | `scores.npz` | Specifically the binder–target ipTM, not contaminated by other chains. |
| **Clash flag** | `scores.npz` | `has_inter_chain_clashes` must be False. |
| **Pose RMSD across samples** | compute yourself | If the 5 diffusion samples all converge to the same pose, that's a strong signal. Wide spread = unreliable. |
| **AF2 self-consistency** | `alphafold` skill | Re-fold the same complex with AF2 and check pose agreement. |

The recommended pattern is to **gate on Chai metrics first** (cheap,
~30–60 s/design on 1 A100), then run the expensive AF2 / ipSAE checks
on the ~5–10% that pass.

## Composite score (suggested starting point)

```python
import numpy as np

def chai_composite(scores_npz_path, chain_pair=(0,1)):
    s = np.load(scores_npz_path)
    if bool(s["has_inter_chain_clashes"]):
        return -np.inf
    iptm_bt = float(s["per_chain_pair_iptm"][chain_pair])
    ptm     = float(s["ptm"])
    iptm    = float(s["iptm"])
    # Chai's own aggregate, restricted to the binder-target interface:
    return 0.2 * ptm + 0.8 * iptm_bt
```

Stricter still: also require `iptm_bt > 0.6` and mean interface pLDDT
> 70 before considering a design. Tune the threshold on a small known-
positive / known-negative set if you have one.

## End-to-end script for a campaign

```python
from pathlib import Path
from chai_lab.batch import run_batch_inference
import numpy as np

# 1. Fold all designs (one fasta per design)
results = run_batch_inference(
    input_dir=Path("designs/"),
    output_dir=Path("chai_out/"),
    devices="0,1,2,3",
    use_msa_server=False,            # designed binders have no MSA
    num_diffn_samples=5,
    seed=0,
    fasta_names_as_cif_chains=True,
)

# 2. Score
rows = []
for r in results:
    if not r.success:
        continue
    # Pick best of the 5 samples
    best_score = -np.inf
    best_cif = None
    for i in range(5):
        s = np.load(r.output_dir / f"scores.model_idx_{i}.npz")
        if bool(s["has_inter_chain_clashes"]):
            continue
        iptm_bt = float(s["per_chain_pair_iptm"][0,1])  # B vs T
        comp = 0.2 * float(s["ptm"]) + 0.8 * iptm_bt
        if comp > best_score:
            best_score = comp
            best_cif = r.output_dir / f"pred.model_idx_{i}.cif"
    rows.append((r.fasta_file.stem, best_score, best_cif))

# 3. Rank
rows.sort(key=lambda x: -x[1])
for stem, score, cif in rows[:20]:
    print(f"{stem}\t{score:.3f}\t{cif}")
```

Run ipSAE (see the `ipsae` skill) on the top ~20% from this list before
ordering.

## Antibody-specific notes

For antibody design (heavy + light + antigen):

- Three chains: list them in a consistent order. With
  `--fasta-names-as-cif-chains` use `H`, `L`, `T`.
- ipTM-of-interest is `per_chain_pair_iptm[H,T]` and
  `per_chain_pair_iptm[L,T]` — both should look good.
- MSA for the antigen *often* helps even when the Fv has none. Use
  `--use-msa-server` if you can afford the latency.
- Chai-2 (preprint Jul 2025) was specifically validated on zero-shot
  antibody design in a 24-well plate — see
  `examples/predict_structure.py` and the
  [Chai-2 preprint](https://www.biorxiv.org/content/10.1101/2025.07.05.663018).

## Cross-validation with a second tool

Standard QC pipeline for high-stakes campaigns:

1. **Chai-1** (fast, strong) → drop the worst 80%.
2. **AlphaFold2 / AlphaFold-Multimer** (`alphafold` skill) → re-fold
   survivors; require good agreement (pose RMSD, ipTM).
3. **Boltz** (`boltz` skill) → optional third opinion.
4. **ipSAE** (`ipsae` skill) → final ranking.
5. **PyRosetta interface metrics** (dG, SC, dSASA — see `protein-qc`
   skill) on the top candidates.

Then send the survivors to experimental SPR/BLI characterisation.

## Pitfalls

- **Don't fold with the target's MSA + designed binder together with
  `use_msa_server=True` and expect helpful pairing.** Chai will try to
  pair MSAs, won't find any for the designed chain, and the result is
  effectively single-sequence for the binder anyway.
- **Don't trust a single seed.** Run 3 seeds × 5 samples = 15
  predictions per design if you suspect mode collapse.
- **Watch crop-size jumps.** A 200 + 250 = 450-token complex fits crop
  512; adding a 50-residue tag pushes it to 768 and ~2× VRAM. Plan your
  batch sizing.
