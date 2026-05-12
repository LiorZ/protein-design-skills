# Structural templates

Templates give Chai-1 a structural prior for one or more chains. They
are loaded in two steps:

1. An `.m8` file lists template hits — each row pairs a query
   identifier with a template PDB chain.
2. For each hit, Chai loads the corresponding `.cif.gz` from either
   RCSB or a directory you specify with the env var
   `CHAI_TEMPLATE_CIF_FOLDER`.

Cap: **4 templates per chain** (`MAX_NUM_TEMPLATES`). More raises
`UnsupportedInputError`.

## Easiest path — ColabFold templates server

```bash
chai-lab fold --use-msa-server --use-templates-server input.fasta out/
```

This populates `out/msas/all_chain_templates.m8` and downloads
templates from RCSB on demand. Requires `--use-msa-server` because
ColabFold returns templates as part of the MMseqs2 query.

In Python:

```python
candidates = run_inference(
    fasta_file=fasta_path,
    output_dir=out,
    use_msa_server=True,
    use_templates_server=True,
    ...
)
```

## Bring-your-own `.m8` file

```bash
chai-lab fold --template-hits-path my_hits.m8 input.fasta out/
```

When you pass a local `.m8`, query identifiers are matched against the
**FASTA entity names** (not sequence hashes). If you want to match by
sequence hash instead, you must go through `--use-templates-server` or
the Python API and set `use_sequence_hash_for_lookup=True`.

### `.m8` schema

Standard MMseqs2 m8 with columns:

```
query  target  pident  alnlen  mismatch  gapopen  qstart  qend  tstart  tend  evalue  bits
```

Only `query`, `target`, `qstart`, `qend`, `tstart`, `tend` are used.
The `target` is treated as `<PDB_ID>_<CHAIN_ID>` (e.g. `1XYZ_A`).

## Custom (non-RCSB) template structures

Set `CHAI_TEMPLATE_CIF_FOLDER`:

```bash
export CHAI_TEMPLATE_CIF_FOLDER=/path/to/cifs
chai-lab fold --template-hits-path my_hits.m8 input.fasta out/
```

Files must be named `<identifier>.cif.gz` where `<identifier>` matches
the `target` column of the `.m8`. Chai will look in
`$CHAI_TEMPLATE_CIF_FOLDER/<identifier>.cif.gz` first before falling
back to RCSB.

## When templates help

| Scenario | Help? |
|----------|-------|
| Predicting a protein with a close homolog in the PDB | ✓ strong improvement |
| Antibody Fv with a related Fv template | ✓ moderate |
| Protein–small-molecule with a related pocket structure | ~ helps interface geometry |
| De novo / designed protein with no PDB neighbour | ✗ no signal |
| Folding a complex where you have the *isolated* monomer structures | ✓ pass them as templates per chain |

## Caveats

- `--use-templates-server` and `--template-hits-path` are mutually
  exclusive.
- `--use-templates-server` requires `--use-msa-server` (templates come
  through the MSA query).
- Templates must reach the model after CIF parsing. Malformed CIFs
  (missing residues, weird chain IDs) are silently skipped; check the
  log if a template seems ignored.
