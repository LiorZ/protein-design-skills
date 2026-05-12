# Outputs

## Directory layout

```
dump_dir/
├── pdbs/
│   ├── <name>_sample_<seed>.pdb
│   └── <name>_sample_<seed>_ligands.txt        # only when ligands are present
├── sequences/
│   └── <name>_sample_<seed>.txt
└── ERR/
    └── <name>.txt                              # only for failed samples (full traceback)
```

`<name>` is the `name` field from the input JSON job; `<seed>` is the
seed used to generate that sample. When `n_seq_duplicates_per_structure > 1`,
the per-structure sequence file contains multiple records but only one
PDB is written.

`dump_dir` defaults to `./output` (resolved relative to the working
directory when you invoke `runner/inference.py`). Override with
`dump_dir=/some/path`.

## `pdbs/<name>_sample_<seed>.pdb`

A standard ATOM/HETATM PDB file containing:

- The generated **protein backbone + side chains** (when not running
  `bb_only=true`; otherwise the placeholders).
- Any **ligand** atoms (placed coordinates resulting from co-folding).
- Any **ion** atoms.
- Any **nucleic-acid** chain atoms.

Chain IDs are assigned by the dumper. Residue numbering starts at 1.

When `output_format=null` (instead of the default
`unconditional_monomer_protein`), the dumper writes a **CIF** file using
the generic Protenix-style dumper, which embeds richer metadata.

## `pdbs/<name>_sample_<seed>_ligands.txt`

Only written when the job has any ligand. One SMILES per line, with the
prefix `ligand_smiles`:

```
ligand_smiles CC(=O)Oc1ccccc1C(=O)O
ligand_smiles N[C@@H](Cc1ccc(O)cc1)C(=O)O
```

For CCD-code ligands and `FILE_` ligands, DISCO writes the original
specifier (path or CCD), not a generated SMILES — verify formatting if
you're parsing programmatically.

## `sequences/<name>_sample_<seed>.txt`

FASTA-*ish* format. For a single protein-only job:

```
>cogen_seq 0
MKTLVPEGMKTLVPEGMKTLVPEG...
```

When the job contains nucleic acids, the file includes annotation lines
under each `>cogen_seq` record:

```
>cogen_seq 0
MKTLVPEG...
dna_sequence GATTACAGATC
dna_sequence GATCTGTAATC
```

When ligands are present, the file also appends `ligand_smiles` lines
under the *last* record:

```
>cogen_seq 0
MKTL...VPEG

ligand_smiles CC(=O)Oc1ccccc1C(=O)O
```

When `n_seq_duplicates_per_structure > 1`, multiple records appear:

```
>cogen_seq 0
MKTL...VPEG
>cogen_seq 1
GRTL...VPDG
>cogen_seq 2
NRGL...VAEG
```

All records share the **same backbone PDB** — they're independent
sequence draws from the decoder conditioned on the same generated
structure.

### Parsing

The format is not strict FASTA — BioPython's `SeqIO.parse(..., "fasta")`
will misclassify the annotation lines. Parse by line prefix:

```python
def parse_disco_sequences(path):
    records = []
    current = None
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current is not None:
                    records.append(current)
                current = {"header": line[1:], "sequence": "", "dna": [], "rna": [], "ligands": []}
            elif line.startswith("dna_sequence "):
                current["dna"].append(line[len("dna_sequence "):])
            elif line.startswith("rna_sequence "):
                current["rna"].append(line[len("rna_sequence "):])
            elif line.startswith("ligand_smiles "):
                current["ligands"].append(line[len("ligand_smiles "):])
            else:
                current["sequence"] += line
        if current is not None:
            records.append(current)
    return records
```

## `ERR/<name>.txt`

A failure log written when a job raises during inference. Contains:

- The rank that hit the error.
- The exception message.
- A full Python traceback.

Common failure modes:

| Message | Cause |
|---------|-------|
| `Conformer generation failed for input SMILES: ...` | RDKit could not embed the SMILES. Pre-generate a 3D conformer and pass it as `FILE_`. |
| `entity type must be proteinChain, dnaSequence, rnaSequence, ligand or ion` | Misspelled entity key (e.g. `protein` instead of `proteinChain`). |
| `No atom found for <NAME> in entity <N> at position <P>` | `covalent_bonds` references an atom that doesn't exist. Verify the CCD atom name and 1-indexed positions. |
| `Can not create bonds because the "count" of entity X and Y are not equal` | Covalent-bond endpoints have unequal `count`s. |
| `too many smiles ligands` | More than 99 SMILES ligands across one JSON file. |
| `CUDA out of memory` | Sequence too long for available GPU; either chunk into smaller jobs or use `effort=fast`. |

## Run-resume semantics

Before generating a sample, the runner checks:

```python
path = f"{dump_dir}/{sample_name}_sample_{curr_seed}.pdb"
if path.exists():
    logger.info(f"{path} already exists -- skipping")
    continue
```

Implications:

- **Crashing mid-run is safe.** Re-launch the same command; only missing
  samples are regenerated.
- **Renaming a job in the JSON triggers a full re-run** for that job.
- **Changing seeds adds only the new seeds**; previous seeds are kept.
- **Changing inference flags does NOT re-trigger a sample** — DISCO
  trusts the file's existence. Use `rm` or change `dump_dir=` if you
  want to force regeneration with new flags.

## `need_atom_confidence=true`

When set, the dumper writes per-atom confidence values alongside the
summary structure. The exact file naming and shape depend on the
`output_format`:

- `output_format=unconditional_monomer_protein`: per-atom confidence is
  embedded in the dumper's auxiliary outputs.
- `output_format=null` (CIF path): a separate `*_atom_confidence.*` file
  is written.

Read the `DataDumper` implementation at `runner/dumper.py` if you need
the exact schema.

## Aggregating outputs across a run

DISCO doesn't write a summary CSV. To build one, walk `dump_dir/pdbs`
and the matching sequence files:

```python
from pathlib import Path
import re

dump = Path("./output")
rows = []
for pdb in (dump / "pdbs").glob("*_sample_*.pdb"):
    m = re.match(r"(.+)_sample_(\d+)\.pdb$", pdb.name)
    if not m:
        continue
    name, seed = m.group(1), int(m.group(2))
    seq = (dump / "sequences" / f"{name}_sample_{seed}.txt").read_text()
    rows.append({"name": name, "seed": seed, "pdb": str(pdb), "sequence_file": str(dump / "sequences" / f"{name}_sample_{seed}.txt")})
```

For co-designability scoring (refolding with Chai-1 / Boltz / AF2 and
computing RMSD), see [evaluation.md](evaluation.md).
