# Outputs & confidence scores

## Directory layout

`protenix pred -o <out_dir>` writes one sub-tree per job, per seed, per sample:

```
<out_dir>/
└── <name>/                                         # job "name" from the JSON
    └── <seed>/                                      # one per --seeds value
        ├── <name>_<seed>_sample_0.cif               # predicted structure (mmCIF)
        ├── <name>_<seed>_summary_confidence_sample_0.json
        ├── <name>_<seed>_sample_1.cif
        ├── <name>_<seed>_summary_confidence_sample_1.json
        └── ...                                       # --sample N structures
```

- `*_sample_*.cif` — all-atom predicted structure in mmCIF.
- `*_summary_confidence_sample_*.json` — confidence scores for that sample.
- With `--need_atom_confidence true`, additional per-atom confidence is emitted.
- Failed inputs are recorded under `<out_dir>/ERR/<name>.txt` instead of crashing
  the batch (the lower-level runner; the CLI also collects per-JSON errors).

Total structures = (#jobs) × (#seeds) × (`--sample`).

## Summary confidence scores

From `docs/infer_json_format.md`. Each `*_summary_confidence_*.json` contains:

| Score | Direction | Meaning |
|-------|:---------:|---------|
| **`ranking_score`** | higher ↑ | **Headline ranking metric** across samples. Protenix sorts by it (`sorted_by_ranking_score=true`). |
| `plddt` | higher ↑ | Predicted lDDT (per-residue local confidence). |
| `gpde` | lower ↓ | Global Predicted Distance Error. |
| `ptm` | →1 | Predicted TM-score (global fold confidence). |
| `iptm` | →1 | Interface pTM — accuracy of inter-chain interfaces. |
| `chain_ptm` | →1 | Per-chain pTM, shape `[N_chains]`. |
| `chain_pair_iptm` | →1 | Pairwise interface pTM, `[N_chains, N_chains]`. |
| `chain_iptm` | →1 | Mean ipTM per chain, `[N_chains]`. |
| `chain_pair_iptm_global` | →1 | Mean `chain_iptm` per pair; for a small-molecule/ion/bonded-ligand chain `C*` equals its `chain_iptm`. |
| `chain_plddt` | higher ↑ | Per-chain pLDDT, `[N_chains]`. |
| `chain_pair_plddt` | higher ↑ | Pairwise pLDDT, `[N_chains, N_chains]`. |
| `has_clash` | false good | Boolean — steric clashes present. |
| `disorder` | — | Predicted intrinsically disordered/flexible regions. |
| `num_recycles` | — | Recycling steps used. |

## How to rank and read

1. **Pick the best structure:** sort all samples (across seeds) by
   **`ranking_score`** desc, take the top. Output is already ordered by it.
2. **Trust the fold:** high `ptm` and high `plddt`; check `has_clash == false`.
3. **Trust an interface** (binder, complex, protein-ligand pocket): look at
   `iptm`, and the specific `chain_pair_iptm[i][j]` for the two chains you care
   about (a ligand/ion chain is named `C*`). A good global `ptm` with a weak
   pairwise ipTM means the monomers are fine but the interface is uncertain.
4. **Per-region:** `plddt`/`chain_plddt` localize confidence; `disorder` flags
   flexible stretches you shouldn't over-interpret.
5. **Hard targets:** raise `--sample`/`--seeds` and re-rank — accuracy scales
   log-linearly with the sampling budget (see `models.md`).

## Downstream

- The `.cif` feeds any structure tool. For **atomistic ligand-pose / side-chain
  refinement and pose re-scoring** of a predicted pocket, hand it to the
  `placer` skill (note PLACER's input caveats — RCSB-style mmCIF parses best).
- Cross-validate a Protenix fold against `boltz` / `chai-lab` and compare
  confidence — agreement across AF3-class models is a strong signal.
- `protenix json -i prediction.cif` round-trips a structure back to an input JSON.
</content>
