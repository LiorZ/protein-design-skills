# `biotite.database` — fetch & search public databases

Pure HTTP against public REST APIs (no binary, no auth required for fetch). Each
subpackage exposes `fetch(...)` and, where the API supports it, `search(query)`
+ a `Query` builder. `fetch` writes files to `target_path` and returns the path
(or a file-like object if `target_path` is omitted).

```python
import biotite.database.rcsb    as rcsb
import biotite.database.afdb    as afdb
import biotite.database.uniprot as uniprot
import biotite.database.entrez  as entrez
import biotite.database.pubchem as pubchem
```

## RCSB PDB — `rcsb`

### Fetch

```python
path = rcsb.fetch("1AKI", "bcif", target_path="/tmp")     # one id
paths = rcsb.fetch(["1AKI", "4HHB"], "cif", target_path="/tmp")   # many
```

`format`: `"pdb"`, `"cif"` / `"mmcif"` / `"pdbx"`, `"bcif"` (BinaryCIF — smallest),
`"fasta"`. `gzip=True` keeps files compressed.

### Search

```python
from biotite.database.rcsb import FieldQuery, BasicQuery, search, count

# free-text
ids = search(BasicQuery("lysozyme"))

# structured field query (combine with & | , negate with ~)
q = (
    FieldQuery("rcsb_entity_source_organism.scientific_name", exact_match="Homo sapiens")
    & FieldQuery("rcsb_entry_info.resolution_combined", less_or_equal=2.0)
    & FieldQuery("exptl.method", exact_match="X-RAY DIFFRACTION")
)
ids = search(q)
n   = count(q)                              # how many, without pulling all ids
```

`FieldQuery` operators: `exact_match`, `contains_words`, `contains_phrase`,
`greater`, `less`, `greater_or_equal`, `less_or_equal`, `equals`, `range`,
`range_closed`, `is_in`.

Specialized queries:
- `SequenceQuery(sequence, scope, min_identity=0.9, max_expect_value=...)` —
  MMseqs2 similarity; `scope` ∈ `"protein"`/`"dna"`/`"rna"`.
- `StructureQuery(pdb_id, chain=... | assembly=...)` — structural similarity.
- `MotifQuery(pattern, pattern_type, scope)` — `pattern_type` ∈
  `"simple"`/`"prosite"`/`"regex"`.

`search(query, return_type="polymer_entity", sort_by=..., group_by=...)` to
return entities/chains instead of whole entries.

## AlphaFold DB — `afdb`

```python
path = afdb.fetch("P12345", "cif", target_path="/tmp")
```

IDs: a UniProt accession (`"P12345"`), an AlphaFold id (`"AF-P12345-F1"`), or the
RCSB computed-model id. `format`: `"pdb"`, `"cif"`/`"mmcif"`/`"pdbx"`, `"bcif"`,
`"fasta"`. (For the predicted-aligned-error / pLDDT extras, fetch the model and
read `b_factor` for pLDDT; PAE is served as a separate JSON by the AFDB API.)

## UniProt — `uniprot`

```python
path = uniprot.fetch("P69905", "fasta", target_path="/tmp")    # .fasta/.txt/.xml/.gff/.rdf
from biotite.database.uniprot import SimpleQuery, search
ids = search(SimpleQuery("kinase") & SimpleQuery("Homo sapiens"))
```

Database (UniProtKB / UniRef / UniParc) is inferred from the id prefix.

## NCBI Entrez — `entrez`

```python
# fetch by UID(s) from a named database
path = entrez.fetch("1234567", target_path="/tmp", suffix="fa",
                    db_name="protein", ret_type="fasta", ret_mode="text")
# search -> UIDs
from biotite.database.entrez import SimpleQuery, search
uids = entrez.search(SimpleQuery("BRCA1") & SimpleQuery("Homo sapiens", field="Organism"),
                     db_name="protein")
```

- `db_name` accepts the E-utility name; `get_database_name("Nucleotide")` maps
  common names (→ `"nuccore"`).
- **API key** raises rate limits: `entrez.set_api_key("...")` (session-scoped).
- `entrez.fetch_single_file(uids, ...)` bundles many UIDs into one file.

## PubChem — `pubchem`

```python
from biotite.database.pubchem import SmilesQuery, NameQuery, search
cids = search(NameQuery("aspirin"))                 # -> compound ids (ints)
cids = search(SmilesQuery("CC(=O)Oc1ccccc1C(=O)O"))
path = pubchem.fetch(cids[0], "sdf", target_path="/tmp")        # 3D coords + bonds
props = pubchem.fetch_property(cids, ["MolecularWeight", "CanonicalSMILES"])
```

Query types: `NameQuery`, `SmilesQuery`, `InchiQuery`, `InchiKeyQuery`,
`FormulaQuery`, `SuperstructureQuery`, `SubstructureQuery`,
`SimilarityQuery(mol, threshold)`, `IdentityQuery`. PubChem rate-limits — Biotite
auto-throttles.

## Patterns

- **Get a target to design against** (`boltzgen`/`disco`): `rcsb.search` to find
  the entry → `rcsb.fetch(id, "bcif")` → load → filter to the chain you want.
- **Pull a ligand for a complex** (`boltz`/`chai-lab`/`protenix`): `pubchem`
  name/SMILES → `fetch(cid, "sdf")` → RDKit bridge or read its bonds.
- **Build an MSA seed set:** `uniprot`/`entrez` search → `fetch("fasta")` →
  align (`sequence.md` / `applications.md`).
