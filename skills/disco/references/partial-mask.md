# Partial-mask design (fix some residues, design the rest)

DISCO accepts mixed sequences where some residues are fixed by their
single-letter code and others are masked with `-`. The masked positions
are generated; the fixed positions are conserved.

## Why partial masking matters

Common scenarios:

- **Fix the N- and C-terminal motif** (signal peptide, helical anchor,
  C-terminal degron). Design the body.
- **Fix a known active-site motif** (e.g. a catalytic triad, a
  metal-binding loop). Design the surrounding scaffold.
- **Fix hotspot residues that must contact a ligand** (e.g. a
  glycine-rich phosphate loop). Let DISCO co-design the rest of the
  pocket.
- **Sequence redesign**: fix most of the sequence, mask out a small
  region (e.g. a loop) and let DISCO regenerate it.

## How it works

Inside `proteinChain.sequence`:

| Character | Meaning |
|-----------|---------|
| `A R N D C Q E G H I L K M F P S T W Y V` | Fixed residue (one-letter code) |
| `X` | Unknown — treated like masked, but flagged as "unknown" in output |
| `-` | **Masked** — DISCO designs this position |

The chain *length* is `len(sequence)`. Position indices (used in
covalent_bonds) are 1-indexed.

## Patterns

### Fix terminal motifs, design the middle

```json
{"proteinChain": {"sequence": "MKTL----------------VPEG", "count": 1}}
```

Designs 16 middle residues, keeps `MKTL` and `VPEG`.

### Fix a hotspot, design everything else

```json
{"proteinChain": {"sequence": "---------------H-----------H------------------", "count": 1}}
```

Two His hotspots at positions 16 and 28 (1-indexed). Useful for
ion-coordination motifs.

### Sequence redesign of a loop

Suppose your starting sequence is 100 residues and you want to
redesign residues 45–55:

```
original:  MKTL...XXXXXXXX...PRSE...   (100 residues)
input:     MKTL...---------...PRSE...   (same length, residues 45-55 → '-')
```

Result: DISCO regenerates positions 45–55, keeping the rest fixed.

## Example: heme + Cys hotspot enzyme

```json
[
  {
    "name": "heme_with_cys_hotspot",
    "sequences": [
      {"proteinChain": {
        "sequence": "------------------------------C-------------------------------------------------------------------------------------------------------------------------------------------------------",
        "count": 1
      }},
      {"ligand": {
        "ligand": "FILE_studio-179/priority_1/heme_b_final_0.sdf",
        "count": 1
      }}
    ],
    "covalent_bonds": [
      {
        "left_entity": 1, "left_position": 31, "left_atom": "SG",
        "right_entity": 2, "right_position": 1, "right_atom": "FE"
      }
    ]
  }
]
```

The Cys at position 31 is fixed; DISCO designs everything else *and*
respects the covalent SG–Fe bond.

A ready-to-edit version is at
[`examples/partial_mask_hotspot.json`](../examples/partial_mask_hotspot.json).

## Counting positions

Use 1-indexed counting. Tools:

```python
seq = "MKTL----------------VPEG"
for i, c in enumerate(seq, start=1):
    print(i, c)
```

Or in zsh:

```zsh
echo "MKTL----------------VPEG" | awk '{for(i=1;i<=length($0);i++) print i, substr($0,i,1)}'
```

## Hard rules

1. **The sequence length is fixed.** Hyphens do not "expand" — they
   count toward the protein length 1:1.
2. **Mixing `-` and explicit letters is the *only* way to do partial
   redesign.** There's no separate "fixed positions" config.
3. **Fixed positions are not regenerated even when `allow_remasking=true`**
   — the path-planning sampler is informed of which positions are
   fixed. (Set `sequence_sampling_strategy.should_ensure_unmasked_stay=true`
   if you want extra defense.)
4. **`covalent_bonds` references are by position in the *full* sequence**,
   not by position among the fixed residues.
5. **Hotspots that pin the model into an infeasible region cause
   refold failures.** If many of your designs fail co-designability,
   your hotspot constraints might be too aggressive. Loosen and re-run.

## Tips

- **Start from a wide mask.** Initially design with as few fixed
  residues as possible, then iteratively tighten if you need motif
  preservation.
- **Combine with `n_seq_duplicates_per_structure`.** Once you have a
  good backbone with fixed hotspots, sample several sequence
  realisations on top.
- **Use partial masking, not `covalent_bonds`, for *fixing residue
  identity* without enforcing a 3D bond.** `covalent_bonds` is a
  3D-geometry constraint, partial-mask is a *sequence* constraint.
- **Mind position numbering when sharing JSONs.** Editing the sequence
  shifts positions and breaks `covalent_bonds` indices silently.
