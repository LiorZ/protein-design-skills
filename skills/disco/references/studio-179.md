# Studio-179 — the ligand-conditioned benchmark

Studio-179 is the benchmark introduced in the DISCO paper for evaluating
ligand-conditioned generative protein design. It is **170 single
ligands + 9 multi-ligand combinations** = 179 jobs total, organized by
priority tier and reproduced in this repo under `studio-179/`.

## What's included

| Tier | Path | Purpose |
|------|------|---------|
| `priority_0` | `studio-179/priority_0/` | Reactive intermediates — used as the conditioning target for the heme-enzyme experiments. Currently: `carbene_v1_ethyl_diazoacetate_3-TS1_heme_guess_nohist.sdf`. |
| `priority_1` | `studio-179/priority_1/` | Core cofactors and binding-relevant ligands (heme B, ATP, ADP, PLP, biotin, BODIPY, etc.). |
| `priority_2` | `studio-179/priority_2/` | Pharmaceuticals, persistent pollutants, organometallic catalysts, idealized metals (Co, Fe, Hg, Pb), Ru / Ir complexes. |
| `priority_3` | `studio-179/priority_3/` | Long tail — natural products, signaling molecules, fluorophores, drugs. |

The full list spans:

- **Rigid molecules** (e.g., tetrachlorodibenzodioxin),
- **Large / flexible molecules** (e.g., CoQ10 — 50 heavy atoms, long
  isoprenoid tail),
- **Metals and metalloclusters** (e.g., [4Fe-4S], idealized Fe / Co / Hg / Pb),
- **Photoredox catalysts** (Ru(bpy), Ir-piano, BODIPY, eosin Y, 4CzIPN),
- **Reactive intermediates** for catalysis design (priority_0).

Each ligand is provided as a 3D-embedded SDF.

## Pre-built input JSONs

Four splits, designed for parallel execution across nodes:

```
input_jsons/all_priorities_ligands_split_0.json
input_jsons/all_priorities_ligands_split_1.json
input_jsons/all_priorities_ligands_split_2.json
input_jsons/all_priorities_ligands_split_3.json
```

Each split contains jobs at **lengths 150, 200, 250** for every ligand
in its share — the canonical benchmark configuration.

Run a split:

```bash
python runner/inference.py \
  experiment=diverse \
  effort=max \
  input_json_path=input_jsons/all_priorities_ligands_split_0.json \
  seeds=\[$(seq -s "," 0 4)\]
```

5 seeds × 3 lengths × all ligands in the split = total samples. For
paper-quality you typically want **5 seeds per (ligand, length)** so the
co-designability denominator is sensible.

## Running a single ligand at benchmark settings

Mirror the structure of `input_jsons/heme_b.json`: three jobs at lengths
150, 200, 250 each referencing the same SDF. The example file
[`examples/single_ligand_studio179.json`](../examples/single_ligand_studio179.json)
is ready to adapt.

Minimum template:

```json
[
  {
    "name": "length_150_<your_ligand>",
    "sequences": [
      {"proteinChain": {"sequence": "<150 hyphens>", "count": 1}},
      {"ligand":       {"ligand": "FILE_studio-179/priority_X/<your_ligand>.sdf", "count": 1}}
    ]
  },
  {
    "name": "length_200_<your_ligand>",
    "sequences": [
      {"proteinChain": {"sequence": "<200 hyphens>", "count": 1}},
      {"ligand":       {"ligand": "FILE_studio-179/priority_X/<your_ligand>.sdf", "count": 1}}
    ]
  },
  {
    "name": "length_250_<your_ligand>",
    "sequences": [
      {"proteinChain": {"sequence": "<250 hyphens>", "count": 1}},
      {"ligand":       {"ligand": "FILE_studio-179/priority_X/<your_ligand>.sdf", "count": 1}}
    ]
  }
]
```

Use `experiment=diverse` and `effort=max` to make your numbers
comparable to the paper.

## The co-designability metric

For each `(ligand, length, seed)`:

1. **Generate** with DISCO → `pdbs/length_X_lig_sample_S.pdb` +
   `sequences/length_X_lig_sample_S.txt`.
2. **Refold** the generated sequence + the original ligand using
   **Chai-1**.
3. Compute:
   - **Protein backbone RMSD** between the DISCO PDB and the Chai-1 PDB.
   - **Per-ligand centroid RMSD** between corresponding ligands.
4. **Pass** iff both backbone RMSD and *every* ligand-centroid RMSD are
   **< 2 Å**.

The benchmark reports the fraction of generated samples that are both
**co-designable** *and* **structurally diverse** (i.e. unique fold
clusters). See [evaluation.md](evaluation.md) for an end-to-end recipe
using the `chai` skill.

## Comparing against the paper

DISCO is reported as state-of-the-art on **178 / 179** ligands and the
DNA / RNA targets. To get apples-to-apples numbers:

- Use **`experiment=diverse`** and **`effort=max`** — both are required.
- Use **at least 5 seeds per (ligand, length)** at the **three lengths**
  150, 200, 250.
- Refold with **Chai-1** (not AF2 or Boltz). Configure Chai-1 to take
  the same ligand conformer as input. The `chai` skill has a recipe.
- Report **fraction co-designable and diverse**, not just plddt / ipTM.

## Raw paper outputs

The raw generations and result spreadsheets for *every* in-silico
experiment in the paper are on HuggingFace:

[`DISCO-Design/DISCO_benchmark_data`](https://huggingface.co/datasets/DISCO-Design/DISCO_benchmark_data)

Use this dataset when you want to:

- Reproduce a specific paper figure without re-running DISCO.
- Score a competing method against the exact same generation pool.
- Sanity-check your own metric implementations against the paper's.

## Tips for a custom screen

- **Start small.** Run 1 seed at length 200 first; verify the pipeline
  before scaling to 5 seeds × 3 lengths.
- **Watch for OOM.** Length 250 + heavy ligands (50+ atoms) needs A100/L40S+.
  On 24 GB cards, drop to `effort=fast` for the prototype iteration.
- **Sweep more lengths if your ligand is unusual.** Studio-179 fixes
  150 / 200 / 250 for comparability, but for tricky targets a wider
  sweep (100 / 150 / 200 / 250 / 300) often surfaces fold solutions the
  canonical lengths miss.
- **Co-designability ≠ activity.** A design passing the 2 Å RMSD filter
  is a *structural* pass. Functional activity (catalysis, binding
  affinity) requires wet-lab follow-up.
