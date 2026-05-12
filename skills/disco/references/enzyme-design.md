# Enzyme design with DISCO

DISCO's flagship wet-lab result is **de novo heme-enzyme design for
new-to-nature carbene-transfer chemistry**, conditioning *solely* on a
3D model of the reactive intermediate. No catalytic residues are
pre-specified, no template scaffold is supplied — DISCO co-designs both
the sequence and the structure of the active site simultaneously.

This page describes how to set up similar enzyme-design jobs.

## Why DISCO works for enzymes

Most enzyme-design pipelines start from a known scaffold and graft a
function. DISCO's joint diffusion lets the sequence and structure
inform each other from t=1 onward, so the active-site geometry can
*emerge* from the conditioning rather than being imposed by a template.
The model has already seen heme-binding proteins, [4Fe-4S]-cluster
proteins, etc. during training, so when you condition on a heme +
substrate transition-state intermediate it tends to place a coordinating
residue (His / Cys / Met) on the proximal face.

The paper demonstrates:

- **Alkene cyclopropanation** (carbene transfer)
- **Spirocyclopropanation**
- **B–H insertion**
- **C(sp³)–H insertion**

Top designs **exceeded** the activity of previously-engineered
heme-based enzymes, and **4× activity gains** were obtained from random
mutagenesis of one design — i.e. the designs are **evolvable**, which is
a non-trivial criterion (overfit designs often aren't).

## Recipe

### 1) Prepare the reactive-intermediate SDF

You need a 3D structure of the **transition-state (TS)** geometry — *not*
the substrate alone. Tools:

- DFT (e.g. Gaussian, ORCA) optimization of the TS structure.
- Cluster-model TS guess imported from a literature reference and
  re-optimized.
- The paper provides one ready-to-use example in
  `studio-179/priority_0/carbene_v1_ethyl_diazoacetate_3-TS1_heme_guess_nohist.sdf`.

The SDF **must** contain a 3D conformer. Strip explicit hydrogens *if*
they make the file noisy — DISCO will keep them as long as the atom
indexing is consistent.

If you have an XYZ from DFT, convert:

```bash
obabel ts_guess.xyz -O ts_guess.sdf --gen3d
```

(`--gen3d` is a no-op when 3D coords already exist; it's there to set
the SDF dimension flag.)

### 2) Author the input JSON

Three jobs spanning sensible enzyme sizes — 150, 200, 250 — keeping the
TS as the only ligand:

```json
[
  {
    "name": "carbene_TS1_len_150",
    "sequences": [
      {"proteinChain": {"sequence": "<150 hyphens>", "count": 1}},
      {"ligand":       {"ligand": "FILE_studio-179/priority_0/carbene_v1_ethyl_diazoacetate_3-TS1_heme_guess_nohist.sdf", "count": 1}}
    ]
  },
  {
    "name": "carbene_TS1_len_200",
    "sequences": [
      {"proteinChain": {"sequence": "<200 hyphens>", "count": 1}},
      {"ligand":       {"ligand": "FILE_studio-179/priority_0/carbene_v1_ethyl_diazoacetate_3-TS1_heme_guess_nohist.sdf", "count": 1}}
    ]
  },
  {
    "name": "carbene_TS1_len_250",
    "sequences": [
      {"proteinChain": {"sequence": "<250 hyphens>", "count": 1}},
      {"ligand":       {"ligand": "FILE_studio-179/priority_0/carbene_v1_ethyl_diazoacetate_3-TS1_heme_guess_nohist.sdf", "count": 1}}
    ]
  }
]
```

A ready-to-use example is at
[`examples/enzyme_design_heme_TS.json`](../examples/enzyme_design_heme_TS.json).

### 3) Run with the paper config

```bash
python runner/inference.py \
  experiment=diverse \
  effort=max \
  input_json_path=input_jsons/enzyme_design_heme_TS.json \
  seeds=\[$(seq -s "," 0 49)\] \
  dump_dir=./carbene_designs
```

**50 seeds × 3 lengths = 150 candidates** per intermediate, which is the
order-of-magnitude the paper used.

- **`experiment=diverse`** is mandatory — `designable` is too conservative
  for active-site exploration.
- **`effort=max`** — never use `fast` for enzyme design.
- **Many seeds.** The pass rate for a good carbene-transfer enzyme is in
  the low single digits even with DISCO, so dilute across many seeds.

### 4) Filter the output

A typical filtering pipeline:

1. **Geometric pre-filter on the placed TS.** Reject samples where the
   Fe–C distance falls outside ~1.8–2.4 Å, or where no axial His/Cys/Met
   is within coordination distance of Fe. This drops obviously
   non-functional designs cheaply.
2. **Co-designability refold** with Chai-1 (or Boltz-2) — see
   [evaluation.md](evaluation.md). Strict cutoff: backbone RMSD < 2 Å
   *and* ligand-centroid RMSD < 2 Å.
3. **Biophysical QC** (instability index, pI, cysteine count, polybasic
   clusters, etc.) via the `protein-qc` skill.
4. **MD relaxation** of the top-K. Look for active-site stability and
   substrate-channel patency.
5. **Wet-lab order.** ~50–200 designs is a reasonable initial pool.

### 5) Optional: add an explicit covalent / coordination bond

For a more constrained heme placement, declare the Fe-coordinating
residue with `covalent_bonds`. This requires fixing the coordinator
position in the sequence (`-` → `H` or `C`) and identifying the
1-indexed position:

```json
{
  "name": "carbene_p450like_len_200",
  "sequences": [
    {"proteinChain": {
      "sequence": "------------------------------C-------------------------------------------------------------------------------------------------------------------------------------------------------",
      "count": 1
    }},
    {"ligand": {
      "ligand": "FILE_studio-179/priority_0/carbene_v1_ethyl_diazoacetate_3-TS1_heme_guess_nohist.sdf",
      "count": 1
    }}
  ],
  "covalent_bonds": [
    {
      "left_entity":  1, "left_position":  31, "left_atom":  "SG",
      "right_entity": 2, "right_position": 1,  "right_atom": "FE"
    }
  ]
}
```

Counting: the `C` is at position 31 in the sequence. Adjust to taste.

**Caveat:** explicitly fixing the coordinator constrains DISCO's
exploration — the paper deliberately *avoided* this, letting DISCO
discover the coordinator on its own. Use covalent_bonds when you want
to enforce a specific binding mode for a known reaction, not when you
want to explore.

## Other enzyme classes

DISCO's approach generalizes to any reaction whose TS / intermediate
you can model. Examples to try:

| Reaction | Cofactor / intermediate | Notes |
|----------|-------------------------|-------|
| PLP-dependent transamination | PLP + amino-acid Schiff base | Use `CCD_PLP` plus a `covalent_bonds` link from Lys to PLP's C4A. |
| SAM-dependent methylation | SAM + substrate | Multi-entity ligand: `CCD_SAM` + substrate SMILES. |
| Iron-sulfur radical chemistry | [4Fe-4S] cluster | `CCD_SF4` + cysteine ligation (3-4 covalent bonds). |
| Photoredox carbene | Ir / Ru photocatalyst + diazo | Use `studio-179/priority_2/iridium-piano_final_0.sdf` or `Ru(bpy)`. |
| Cytochrome P450-like O insertion | Heme + oxo-iron / substrate | Build the Cpd I cluster as an SDF; add Cys-Fe covalent bond. |
| Carbonic anhydrase-style hydration | Zn²⁺ + substrate-water | `CCD_ZN` + His ligation via covalent bonds. |

For any of these, the same `experiment=diverse effort=max` recipe applies.
The art is in (a) the TS / intermediate model and (b) the downstream
filtering — DISCO produces the structural hypotheses, your scoring
pipeline ranks them.

## Pitfalls

1. **Conditioning on the substrate, not the TS.** The substrate is
   a *binding* target, not a catalysis target. The model will design a
   binding pocket, not a TS-stabilizing active site. Always condition
   on the TS / intermediate.
2. **Wrong protonation states.** The SDF must reflect the catalytic
   protonation (e.g., neutral histidine in heme proteins). RDKit's
   default protonation is often wrong for active-site chemistry.
3. **Active-site polarity not enforced.** DISCO will produce many
   nonpolar pockets unless your TS / intermediate has unambiguous
   electrostatic features. For polar TSs, expect more useful designs.
4. **Not enough seeds.** Pass rates for enzyme-grade designs are low.
   Plan for 50–200 seeds per length.
5. **No MD validation.** Refolded backbone RMSD < 2 Å says nothing
   about whether the active site is dynamically intact at 300 K.
   For wet-lab decisions, MD-relax and inspect the active site over
   trajectories.
