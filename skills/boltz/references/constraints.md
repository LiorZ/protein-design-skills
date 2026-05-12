# Constraints — bonds, pockets, contacts

Boltz supports three constraint types under the YAML top-level `constraints:` list. All are optional. Indices are **1-based** throughout.

## `bond` — explicit covalent bond

Use this to declare a non-default covalent linkage between two atoms — e.g. a glycoprotein link, a disulfide between non-adjacent cysteines that you want enforced, or a small-molecule ligand covalently attached to a protein residue.

```yaml
constraints:
  - bond:
      atom1: [CHAIN_ID, RES_IDX, ATOM_NAME]
      atom2: [CHAIN_ID, RES_IDX, ATOM_NAME]
```

| Field | What it is |
|-------|------------|
| `CHAIN_ID` | The `id:` of the polymer or ligand entry in `sequences:`. |
| `RES_IDX`  | 1-indexed residue number in that chain. For a ligand (which is exactly one residue), use `1`. |
| `ATOM_NAME` | CCD-standard atom name (case-sensitive). Look it up from the RCSB CCD entry, e.g. `CA`, `CB`, `SG`, `OD1`, `N`, `C`, `O`, `P`. For ligands, atom names come from the CCD component. |

### Hard constraints

- Both endpoints must be **CCD-known** (canonical residue or CCD ligand). SMILES ligands cannot participate in a `bond:` because their atoms have no stable names — declare them as a CCD if you need this.
- The atom names must match the per-residue CCD entry exactly.
- If you specified a `modifications:` on a polymer, the atom names come from the modified residue's CCD (e.g. `SD` and `SE` for MSE).

### Example: disulfide between A:Cys23 and A:Cys87

```yaml
- bond:
    atom1: [A, 23, SG]
    atom2: [A, 87, SG]
```

### Example: glycosylation N-NAG link

```yaml
sequences:
  - protein:
      id: A
      sequence: ...NSS...
  - ligand:
      id: G
      ccd: NAG
constraints:
  - bond:
      atom1: [A, 7, ND2]      # Asn side-chain ND2
      atom2: [G, 1, C1]       # NAG anomeric C1
```

## `pocket` — bias a binder toward a set of residues / atoms

Use this when you know the binding site (from a co-crystal, mutagenesis, an epitope map, or domain expertise) and want the model to land the ligand / partner there.

```yaml
constraints:
  - pocket:
      binder: CHAIN_ID                       # the chain that should bind
      contacts:                              # list of pocket "tokens"
        - [CHAIN_ID, RES_IDX_OR_ATOM_NAME]
        - [CHAIN_ID, RES_IDX_OR_ATOM_NAME]
      max_distance: 6                        # Å; range 4–20, default 6
      force: false                           # if true, enforce via a potential
```

- `binder` may be a `protein`, `dna`, `rna`, or `ligand` chain.
- Each `contacts` entry is `[chain, idx]` for polymer chains, or `[chain, atom_name]` for ligand chains (because ligands have only one residue).
- `max_distance` is the constraint: every contact must be within this Å of *some* atom of the binder.

### Boltz-1 vs Boltz-2 limits

| | Boltz-1 | Boltz-2 |
|---|---|---|
| `max_distance` | must be exactly `6` (else raises) | any value in `[4, 20]` |
| Number of `pocket:` constraints | exactly one | unlimited |

### Hard vs soft

- `force: false` (default) — the pocket signal goes into the trunk as a featurized "you should touch these residues" hint. The diffusion sampler is *biased* but not constrained.
- `force: true` — adds a steering potential during diffusion that penalises deviations from the constraint. Use this when the experimental signal is strong (e.g. confirmed cocrystal pocket).

### Example: small molecule into a known site

```yaml
sequences:
  - protein:
      id: A
      sequence: MVTPEGNVSLVDESLLVGVTDED...
      msa: ./msa_A.a3m
  - ligand:
      id: L
      smiles: 'N[C@@H](Cc1ccc(O)cc1)C(=O)O'
constraints:
  - pocket:
      binder: L
      contacts:
        - [A, 138]
        - [A, 142]
        - [A, 169]
      max_distance: 6
      force: false
```

### Example: peptide binder onto an epitope

```yaml
sequences:
  - protein:                  # target
      id: A
      sequence: ...
  - protein:                  # designed binder
      id: B
      sequence: ...
constraints:
  - pocket:
      binder: B
      contacts:
        - [A, 829]
        - [A, 138]
```

## `contact` — bias a single token-token contact (Boltz-2 only)

Lighter-weight than `pocket` when you only know one pairing (e.g. a specific cross-linking constraint, or a single hotspot).

```yaml
constraints:
  - contact:
      token1: [CHAIN_ID, RES_IDX_OR_ATOM_NAME]
      token2: [CHAIN_ID, RES_IDX_OR_ATOM_NAME]
      max_distance: 6                  # Å, default 6
      force: false
```

The two tokens can be on the same chain (e.g. a long-range intra-chain contact from chemical cross-linking) or different chains. Same coordinate convention as `pocket.contacts`.

**Raises** when `--model boltz1` — Boltz-1 has no per-pair contact head.

### Example: cross-link constraint from MS

```yaml
- contact:
    token1: [A, 42]
    token2: [A, 211]
    max_distance: 11           # typical for DSS/BS3 cross-linker reach
    force: true
```

## Combining constraints

You can mix any number of `bond`, `pocket`, and `contact` entries in one YAML, and pair them with `templates:` and `properties.affinity`. Constraints are independent; they all add to the same featurization / potential stack.

A common recipe for a covalent inhibitor:

```yaml
sequences:
  - protein: { id: A, sequence: ..., msa: ./msa.a3m }
  - ligand:  { id: L, ccd: COV_LIGAND_CCD }
constraints:
  - pocket:                        # know the pocket
      binder: L
      contacts: [[A, 138], [A, 142], [A, 169]]
      max_distance: 6
  - bond:                          # and the warhead covalent link
      atom1: [A, 169, SG]          # Cys169 thiol
      atom2: [L, 1, C12]           # warhead acrylamide carbon
```

## Choosing distances

The model is robust to soft constraints. As a heuristic:

| Scenario | `max_distance` |
|----------|----------------|
| Direct contact you're sure about | 4–5 Å |
| Default / unknown | 6 Å |
| Loose epitope / domain proximity | 10–15 Å |
| Long-range crosslinker (DSS, BS3) | 11–14 Å |
| Loose tether (gel filtration, HDX) | up to 20 Å |

Tightening `max_distance` increases the strength of the bias (and the penalty when `force: true`).
