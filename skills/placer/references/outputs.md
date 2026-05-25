# Outputs and confidence scores

## Files

For each input, `run_PLACER.py` (and `PLACER.protocol.dump_output`) writes two
files with the prefix `<odir>/<input_stem>[_<suffix>]`:

| File | Contents |
|------|----------|
| `<prefix>_model.pdb` | **Multimodel** PDB — one `MODEL`/`ENDMDL` block per sample. Reranked best→worst when `--rerank` is set. The **per-atom `prmsd` is written to the b-factor column**, so you get per-residue/per-atom confidence directly. |
| `<prefix>.csv` | One row per sample, columns = the per-model scores below (it omits the bulky array fields like coordinates, plDDTs, pDEVs). |

The console prints model indices as they are generated; **after `--rerank` those
indices no longer match file order** — trust the CSV ordering and the MODEL
numbering in the output PDB, not the live log.

## Scores (CSV columns)

| Score | What it is | Direction | Comparison? |
|-------|-----------|-----------|-------------|
| `prmsd` | **Predicted** RMS of atomic-position deviations of the ligand — the model's own uncertainty estimate. | lower = better | self-reported confidence (no ground truth) |
| `plddt` | Predicted lDDT averaged over ligand atoms, from the network's **1D track**. | higher = better | confidence |
| `plddt_pde` | Predicted lDDT averaged over ligand atoms, from the **2D track**. | higher = better | confidence |
| `fape` | All-atom FAPE loss vs. the input structure. | lower = better | vs. input (ground-truth-relative) |
| `lddt` | Actual all-atom lDDT between model and the input structure. | higher = better | vs. input |
| `rmsd` | Ligand-atom RMSD between input (ground truth) and prediction — docking-position accuracy. | lower = better | vs. input |
| `kabsch` | Superimposed (Kabsch-aligned) ligand-atom RMSD — conformation accuracy independent of placement. | lower = better | vs. input |

### Which score to use

- **Docking / blind pose ranking → `prmsd`.** It needs no ground truth, so it is
  the right confidence for real predictions. `rerank prmsd`.
- `plddt` / `plddt_pde` are secondary confidences — use them to break ties and
  to sanity-check a borderline `prmsd`.
- `fape` / `lddt` / `rmsd` / `kabsch` all compare to the **input** structure.
  They're meaningful only when you trust the input pose (e.g. benchmarking
  against a crystal structure), not for de novo docking where the input is just
  a starting guess.

### Reading `prmsd` (upstream guidance)

- `prmsd < 2.0` → trustworthy.
- `prmsd < 4.0` → acceptable if it's the best available **and** `plddt`,
  `plddt_pde` are good (`> 0.8`).
- A "good" `prmsd` scales with molecule complexity — larger/more-symmetric
  ligands have higher baseline `prmsd`.

## Recommended workflow

1. Generate an ensemble: `-n 50` (sidechains) or `-n 50..100` (docking; `>200`
   for hard ligands).
2. `--rerank prmsd`.
3. Analyze the **top ~10%** by `prmsd` — that's where the trustworthy poses are.
4. For per-residue confidence, read the b-factor column of `*_model.pdb`.

## How many samples?

| Task | Samples |
|------|---------|
| Sidechain conformation analysis | ~50 |
| Ligand docking | 50-100 |
| Hard ligands (few high-confidence hits) | >200 |

Per-model time: ~1-3 s on GPU (depends on the card and ligand automorphism
count); ~7 min on 1 CPU core, ~1 min on 8 cores. Ligands with many symmetric
groups (automorphisms) take longer.
