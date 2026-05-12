# Templates (Boltz-2 only)

Templates let you condition the prediction on a known structure (a cocrystal, an apo state, a related homolog). They live under the YAML top-level `templates:` list.

```yaml
templates:
  - cif: /abs/or/relative/path/to/template.cif
  - cif: another.cif
    chain_id: A
  - cif: another.cif
    chain_id: [A, B]
    template_id: [X, Y]
  - pdb: legacy.pdb
    chain_id: [A, B]
    template_id: [A1, A2]
  - cif: hard.cif
    force: true
    threshold: 2.0
```

Each entry must have **either** `cif:` **or** `pdb:` (not both).

## Field reference

| Field | Meaning |
|-------|---------|
| `cif` | Path to an mmCIF file. |
| `pdb` | Path to a PDB file. PDB chains are renamed incrementally as `A1`, `A2`, ..., `B1`, ... by the parser; use those names in `template_id`. |
| `chain_id` | Which chain(s) in **your YAML** should receive this template. `str` or list. If omitted, every protein chain in the YAML is a candidate. |
| `template_id` | Which chain(s) in **the template file** to use, paired positionally to `chain_id`. If omitted, Boltz picks the best-matching template chain by global alignment. |
| `force` | If `true`, apply a backbone-RMSD potential during diffusion. Default `false`. |
| `threshold` | Required when `force: true`. Maximum allowed backbone deviation, in Å. |

## How matching works

When you give *both* `chain_id` and `template_id` and the lengths match, Boltz uses that explicit mapping directly. Lengths must be equal — otherwise it raises.

When `template_id` is omitted (with or without `chain_id`), Boltz runs:

1. For each `(query_chain, template_chain)` pair, a **global alignment** (Biopython `PairwiseAligner`) scores compatibility.
2. The Hungarian / assignment-style match picks the best mapping.
3. **Local alignments** within each picked pair determine which residues are covered.

This is identical in spirit to the AF2/AF3 template-search pipeline, but operates only over the chains in the file you provide — there is no server-side PDB scan.

## Hard rules

- Templates are **Boltz-2 only**. With `--model boltz1` the parser raises `Templates are not supported in Boltz 1.0!`.
- Only protein chains in both the query and template are used. DNA / RNA / ligand chains in the template file are ignored.
- `chain_id` must be a `protein` chain in your YAML.
- `template_id` must be a protein chain in the template file (or a renamed PDB sub-chain like `A1`, `A2`).
- `force: true` without `threshold` raises.

## When to use `force`

- **`force: false` (default)** — the template biases the trunk. Good when the template is a "useful hint" (a homolog, an apo state of the same protein, a closely related structure). The diffusion sampler is free to move backbone atoms wherever the energy / data signal pulls them.
- **`force: true` + `threshold: X`** — the diffusion sampler is *constrained* to stay within X Å backbone RMSD of the template. Use when you want to lock the backbone (e.g. predicting a ligand into a known holo pocket; predicting an antibody Fv in a known canonical loop conformation).

Typical thresholds:

| Goal | `threshold` |
|------|------------|
| Loose tether to the homolog | 4–6 Å |
| Tight constraint to an apo state | 2 Å |
| "Rigid scaffold, model only the loops/ligand" | 1–1.5 Å |

## Examples

### Single homolog template

```yaml
templates:
  - cif: ./templates/2abc.cif
```

Boltz aligns every protein chain in your YAML against every protein chain in `2abc.cif` and picks the best matching pairs.

### Restrict to a specific chain

```yaml
templates:
  - cif: ./templates/2abc.cif
    chain_id: A
```

Only your chain A gets templated; the best-matching chain in `2abc.cif` is chosen.

### Explicit mapping

```yaml
templates:
  - cif: ./templates/heterodimer.cif
    chain_id: [A, B]
    template_id: [H, L]   # template's heavy + light → your A + B
```

Order matters — the list is positional.

### Hard template for a known apo backbone

```yaml
templates:
  - cif: ./templates/apo.cif
    chain_id: A
    force: true
    threshold: 1.5
```

### Multiple templates

```yaml
templates:
  - cif: ./templates/apo.cif         # for your chain A
    chain_id: A
  - cif: ./templates/partner.cif     # for your chain B
    chain_id: B
```

You can also have multiple template entries match the same chain — each contributes independently to the trunk featurisation.

## PDB vs CIF

CIF is preferred. If you must use a PDB:

- Chains in the original PDB are split into sub-chains by SEQRES boundaries and renamed `A1`, `A2`, `B1`, ... Use those names in `template_id`.
- TER records and HETATMs are parsed as in PDB conventions.

```yaml
templates:
  - pdb: ./templates/legacy.pdb
    chain_id: [A, B]
    template_id: [A1, B1]
```

## Caveats

- Templates are not a replacement for an MSA — you still want `--use_msa_server` (or a local `.a3m`) on the protein chains.
- A poor template can hurt the prediction, especially without `force`. Prefer high-identity homologs (> 30% seq id).
- Boltz-2 was trained with up to a few templates per chain; pushing many more is fine but yields diminishing returns.
- There is no automated "search the PDB" — you choose the templates upfront. For automated template search, run an HMMer / Foldseek pipeline first and feed the top hits in.
