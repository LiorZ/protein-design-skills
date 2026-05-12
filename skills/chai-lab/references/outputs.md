# Outputs and scoring

A successful `chai-lab fold` writes the following files into the output
directory:

```
out/
├── pred.model_idx_0.cif         # candidate 0 structure
├── pred.model_idx_1.cif
├── pred.model_idx_2.cif
├── pred.model_idx_3.cif
├── pred.model_idx_4.cif
├── scores.model_idx_0.npz       # per-candidate metrics
├── scores.model_idx_1.npz
├── scores.model_idx_2.npz
├── scores.model_idx_3.npz
├── scores.model_idx_4.npz
├── msa_depth.pdf                # only if MSAs were used
└── msas/                        # only if --use-msa-server
    ├── <hash>.aligned.pqt
    └── all_chain_templates.m8
```

With `num_trunk_samples > 1`, files are nested under `trunk_0/`,
`trunk_1/`, … inside `out/`.

## The CIF files

Standard mmCIF with:

- One model, multiple chains.
- Chain IDs `A, B, C, …` in FASTA order (or your `name=` values if
  `--fasta-names-as-cif-chains` was set).
- **B-factor column = pLDDT scaled to 0–100** (higher = more confident).
- Ligands appear as HETATM with the SMILES-derived atom names.
- Modified residues use their CCD codes (e.g. `MSE`).
- Glycans appear as a separate chain with their CCD codes (`NAG`,
  `BMA`, `MAN`, …).

Load with any standard tool: PyMOL `load`, ChimeraX `open`,
`biotite.structure.io.pdbx`, `gemmi.read_structure`, `mmcif_pdbx`, etc.

## The `scores.model_idx_*.npz` files

Each `scores.model_idx_<i>.npz` is the dict returned by
`chai_lab.ranking.rank.get_scores(ranking_data)`:

| Key | Shape | Meaning |
|-----|-------|---------|
| `aggregate_score` | `(1,)` | Headline ranking number (higher is better). Formula: `0.2 * ptm + 0.8 * iptm - 100 * has_inter_chain_clashes` |
| `ptm` | `(1,)` | Complex pTM, 0–1 |
| `iptm` | `(1,)` | Interface pTM, 0–1 |
| `per_chain_ptm` | `(n_chains,)` | pTM restricted to each chain |
| `per_chain_pair_iptm` | `(n_chains, n_chains)` | ipTM for each chain pair |
| `has_inter_chain_clashes` | `(1,)` bool | Hard clash flag; triggers the `-100` penalty |
| `chain_chain_clashes` | `(n_chains, n_chains)` int | Per-pair atom-clash counts |

Load:

```python
import numpy as np
s = np.load("out/scores.model_idx_0.npz")
print(float(s["aggregate_score"]), float(s["ptm"]), float(s["iptm"]))
```

## The `StructureCandidates` Python object

What `run_inference` returns. In addition to the per-sample npz fields,
this object also exposes per-token tensors that are **not** saved to
disk:

| Attribute | Shape | Meaning |
|-----------|-------|---------|
| `cif_paths` | `list[Path]` | One path per candidate |
| `ranking_data` | `list[SampleRanking]` | Per-candidate ranking dataclasses (rich) |
| `msa_coverage_plot_path` | `Path \| None` | PDF coverage plot if MSAs were used |
| `pae` | `(cands, tokens, tokens)` | Predicted Aligned Error in Å (capped at 32) |
| `pde` | `(cands, tokens, tokens)` | Predicted Distance Error in Å |
| `plddt` | `(cands, tokens)` | Per-token pLDDT on 0–1 scale |

If you need to persist these too, e.g. for downstream interface
analysis:

```python
import numpy as np
np.savez(out_dir / "pae_pde_plddt.npz",
         pae=result.pae.numpy(),
         pde=result.pde.numpy(),
         plddt=result.plddt.numpy())
```

## How to rank candidates

Default: pick `argmax(aggregate_score)` across the candidates. This is
what `candidates.sorted()[0]` returns.

```python
top = result.sorted()
print("Best:", top.cif_paths[0])
print("Score:", float(top.ranking_data[0].aggregate_score))
```

## How to interpret the metrics

| Metric | Rough thresholds | What it tells you |
|--------|------------------|-------------------|
| `ptm` (complex pTM) | >0.7 likely correct fold; >0.8 confident | Global fold quality. AF2 / Chai convention. |
| `iptm` (interface pTM) | >0.6 likely real interface; >0.8 strong | Quality of *all* inter-chain contacts together. |
| `per_chain_pair_iptm[i,j]` | as above | Quality of the specific i–j interface. |
| `plddt` (per token) | >70 confident; 50–70 low confidence; <50 disordered | Per-residue trust. Inspect at interface for binder QC. |
| `pae[i, j]` (Å) | <5 Å between two tokens means Chai is confident in their relative pose | Use to find rigid sub-blocks. |
| `pde` | similar to pae | Predicted distance error. |
| `has_inter_chain_clashes` | False expected | If True, the prediction has serious steric clashes; the `-100` aggregate penalty makes such candidates unselectable. |

### For designed binders specifically

ipTM alone consistently overconfidences designed binders. Stronger
options on top of the Chai outputs:

- **ipSAE** — see the `ipsae` skill. Generally a better predictor of
  experimental success than ipTM. Computed from the same Chai PAE +
  CIF outputs.
- **Per-chain-pair ipTM** for the binder–target pair specifically
  (rather than complex-wide ipTM).
- **Interface pLDDT** — average pLDDT over residues within ~5 Å of the
  other chain. Quick and effective filter.
- **Clash flag must be False.**

See [binder-validation.md](binder-validation.md) and the `protein-qc`
skill for full QC pipelines and thresholds.

## The `msa_depth.pdf` plot

A coverage plot of MSAs per token, similar to AlphaFold's. Useful for
diagnosing weak alignments or chain coverage gaps. Only written when at
least one chain had a real MSA.

## Output-directory rule

`run_inference` aborts if `output_dir` already exists and is
**non-empty**. To re-run, either delete the directory or pick a new
one. (`shutil.rmtree(out)` in your script before the call is the
typical pattern.)
