# Nucleic-acid-conditioned design (DNA / RNA binders)

DISCO supports designing single-chain protein binders for fixed DNA or
RNA sequences. The paper demonstrates this on:

| Target | File | Description |
|--------|------|-------------|
| RNA | `input_jsons/6YMC_rna.json` | 26-nt RNA from PDB 6YMC, lengths 50–80 |
| DNA | `input_jsons/7S03_dna.json` | dsDNA from PDB 7S03, lengths 50–80 |

DISCO scores best on RNA and DNA targets as well as on ligands.

## RNA-binding protein design

```json
[
  {
    "name": "rna_binder_len_60",
    "sequences": [
      {"proteinChain": {"sequence": "------------------------------------------------------------", "count": 1}},
      {"rnaSequence":  {"sequence": "GGCUAGCCAUUUGAC", "count": 1}}
    ]
  }
]
```

Alphabet: **A, U, G, C, N** (N = unknown). No masking — every position
must be specified.

```bash
python runner/inference.py \
  experiment=diverse \
  effort=max \
  input_json_path=input_jsons/my_rna_binder.json \
  seeds=\[0,1,2,3,4\]
```

## DNA-binding protein design

`dnaSequence` is a **single strand**. For double-stranded DNA, add the
reverse complement as a second `dnaSequence` entry:

```json
[
  {
    "name": "dna_binder_len_60",
    "sequences": [
      {"proteinChain": {"sequence": "------------------------------------------------------------", "count": 1}},
      {"dnaSequence":  {"sequence": "GATTACAGATC", "count": 1}},
      {"dnaSequence":  {"sequence": "GATCTGTAATC", "count": 1}}
    ]
  }
]
```

(`GATCTGTAATC` is the reverse complement of `GATTACAGATC`.)

Alphabet: **A, T, G, C, N**. No `U`. No masking — every position must be
specified.

## Length sweeps

The paper sweeps protein-chain lengths **50–80** for both DNA and RNA
targets. The pre-built input JSONs (`6YMC_rna.json`, `7S03_dna.json`)
include all 31 lengths in one file.

For your own target, mirror the same pattern:

```json
[
  {"name": "my_binder_50", "sequences": [{"proteinChain": {"sequence": "<50 hyphens>", "count": 1}}, {"rnaSequence": {"sequence": "ACGUACGU...", "count": 1}}]},
  {"name": "my_binder_55", "sequences": [{"proteinChain": {"sequence": "<55 hyphens>", "count": 1}}, {"rnaSequence": {"sequence": "ACGUACGU...", "count": 1}}]},
  {"name": "my_binder_60", "sequences": [{"proteinChain": {"sequence": "<60 hyphens>", "count": 1}}, {"rnaSequence": {"sequence": "ACGUACGU...", "count": 1}}]},
  ...
]
```

Use 5 seeds per length for a screen. The bigger / longer the nucleic
acid, the more protein you typically need.

## Tips

1. **Use `experiment=diverse`, `effort=max`.** Same as ligand
   conditioning — paper defaults.
2. **Avoid masking** in the nucleic acid. The model treats nucleic-acid
   positions as fully specified context.
3. **Don't include both `U` and `T` in the same entity.** `U`s go in
   `rnaSequence`, `T`s in `dnaSequence`. Mixing them in one entity is
   undefined.
4. **For dsDNA, the strands should be reverse complements.** DISCO does
   not enforce this — you can in principle put two non-complementary
   strands, but the resulting prediction will be unrealistic.
5. **5'→3' direction matters.** Both `dnaSequence` and `rnaSequence`
   are 5'→3'. When adding the reverse complement strand, write it in
   its own 5'→3' direction.
6. **Hairpins and other secondary structure** are not explicitly modeled
   — DISCO conditions on the *sequence*, and the predictor places the
   nucleic acid as the joint fold dictates. If you want to enforce a
   secondary structure motif you'll need a more specialized tool
   downstream.
7. **Protein lengths matter.** Too short → can't wrap; too long → may
   not converge. The 50–80 window from the paper is a good first
   bracket.

## Refolding for evaluation

To evaluate co-designability, refold each `(generated_protein_sequence,
original_nucleic_acid_sequence)` pair with Chai-1 (or AF2 / Boltz). The
pass criterion is:

- Backbone RMSD < 2 Å, **and**
- Nucleic-acid centroid distance < 2 Å (vs. the DISCO-placed nucleic
  acid).

See [evaluation.md](evaluation.md) for the recipe.

## Worked example: from PDB to DISCO input

Suppose you want to design a binder for the 19-nt RNA stem-loop of
PDB `1F1T`. Steps:

1. Pull the RNA sequence from the PDB entity. For 1F1T:
   `GGGAACUGAGUUCC` (illustrative).
2. Decide a length sweep: 50, 60, 70.
3. Write JSON:

   ```json
   [
     {"name": "rna_1F1T_50", "sequences": [
       {"proteinChain": {"sequence": "--------------------------------------------------", "count": 1}},
       {"rnaSequence":  {"sequence": "GGGAACUGAGUUCC", "count": 1}}
     ]},
     {"name": "rna_1F1T_60", "sequences": [
       {"proteinChain": {"sequence": "------------------------------------------------------------", "count": 1}},
       {"rnaSequence":  {"sequence": "GGGAACUGAGUUCC", "count": 1}}
     ]},
     {"name": "rna_1F1T_70", "sequences": [
       {"proteinChain": {"sequence": "----------------------------------------------------------------------", "count": 1}},
       {"rnaSequence":  {"sequence": "GGGAACUGAGUUCC", "count": 1}}
     ]}
   ]
   ```

4. Run:

   ```bash
   python runner/inference.py \
     experiment=diverse \
     effort=max \
     input_json_path=input_jsons/rna_1F1T.json \
     seeds=\[0,1,2,3,4\]
   ```

5. Refold each generated sequence with the same RNA in Chai-1 and
   apply the co-designability filter.

Ready-to-use templates: see
[`examples/rna_binder.json`](../examples/rna_binder.json) and
[`examples/dna_binder.json`](../examples/dna_binder.json).
