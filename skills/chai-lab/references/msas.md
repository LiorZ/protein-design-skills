# Providing MSAs

Chai-1 runs fine in "single-sequence mode" (the default), but accuracy
on real complexes improves substantially with MSAs. There are three
ways to provide them:

1. **ColabFold MMseqs2 server** — fully automatic.
2. **A local directory of `.aligned.pqt` files** — one per unique
   protein sequence.
3. **A custom `MSAContext` built in Python** — advanced, via
   `run_folding_on_context`.

## Option 1 — ColabFold server

```bash
chai-lab fold --use-msa-server input.fasta out/
```

Or in Python:

```python
candidates = run_inference(
    fasta_file=fasta_path,
    output_dir=out,
    use_msa_server=True,
    ...
)
```

Chai queries `https://api.colabfold.com` (override with `--msa-server-url`).
Generated MSAs are saved under `out/msas/<hash>.aligned.pqt`. Note the
shared/public server is rate-limited and best-effort; for production
runs host your own ColabFold MMseqs2 server.

Add `--use-templates-server` to also pull structural templates; Chai
writes `out/msas/all_chain_templates.m8`.

## Option 2 — Local `.aligned.pqt` files

```bash
chai-lab fold --msa-directory ./my_msas/ input.fasta out/
```

Chai expects one file per unique protein chain sequence, **named by the
SHA-256 hash of that sequence**: `<sha256>.aligned.pqt`. The package
computes the hash internally; you can replicate it with:

```python
from chai_lab.data.parsing.msas.aligned_pqt import hash_sequence  # name may vary
```

…but the simpler path is to convert from a3m and let Chai write the
hashed filename for you.

### The `.aligned.pqt` schema

A `.aligned.pqt` file is a parquet dataframe with **four columns**:

| Column            | Type | Meaning |
|-------------------|------|---------|
| `sequence`        | str  | One alignment hit in a3m format (uppercase = aligned, lowercase = insertion). First row must be the **query**. |
| `source_database` | str  | One of `uniprot`, `uniref90`, `bfd_uniclust`, `mgnify`, `query`. **This is featurized**, not just metadata. |
| `pairing_key`     | str  | Used to pair MSA rows across chains in a complex (species, OrthoDB ID, …). Empty string = unpaired. |
| `comment`         | str  | Free-form, ignored by the model. |

Toy table:

| sequence | source_database | pairing_key  | comment |
|----------|-----------------|--------------|---------|
| RKDSS... | query           |              | query   |
| RKDES... | uniref90        |              | hit 1   |
| RKSES... | uniprot         | Mus musculus | mouse   |

Hints:

- The query sequence appears **exactly once**, as the first row, with
  `source_database=query`.
- If your alignments came from a database not in the recognised list,
  `uniref90` is a safe catch-all (it's what Chai treats as the default
  source).
- The pairing key matters for multi-chain complexes; sequences with the
  same key across chains get aligned to each other. Species annotation
  is the canonical choice (mirrors AF-Multimer / AF3).

### Convert from a3m

```bash
chai-lab a3m-to-pqt ./a3ms/
```

Each subdirectory is treated as the alignments for a single query.
This uses UniProt species annotations for pairing keys by default.

For programmatic conversion / custom pairing logic:

```python
from chai_lab.data.parsing.msas.aligned_pqt import merge_multi_a3m_to_aligned_dataframe
df = merge_multi_a3m_to_aligned_dataframe({
    "uniref90": "path/to/uniref90.a3m",
    "uniprot":  "path/to/uniprot.a3m",
    # ...
})
df.to_parquet("<hash>.aligned.pqt")
```

### MSA depth cap

Chai caps MSAs at **16,384 rows** (`MAX_MSA_DEPTH`). Deeper alignments
raise `UnsupportedInputError`. Use `recycle_msa_subsample=N` if your
search returned more rows than you want featurised per recycle.

## Option 3 — In-memory `MSAContext`

For exotic alignments (e.g. structure-based MSAs, custom embeddings),
build an `MSAContext` directly and feed it to `run_folding_on_context`.
Look at `chai_lab/data/dataset/msas/msa_context.py` and
`chai_lab/data/dataset/msas/load.py` for the shapes.

## Server selection guidance

| Scenario | Recommendation |
|----------|----------------|
| One-off prototype | `--use-msa-server` |
| Production / many designs | Self-host ColabFold or precompute MSAs and pass `--msa-directory` |
| Antibodies (no useful MSA) | Skip MSAs — single-sequence is fine; lean on `--use-templates-server` if a related Fv exists |
| De novo / designed proteins | Skip MSAs — there is no evolutionary signal |
| MSA causes OOM | Use `recycle_msa_subsample=2048` (or smaller) |

## Caveats

- `--use-msa-server` and `--msa-directory` are mutually exclusive.
- Local MSAs are matched to chains by **sequence hash**, not by entity
  name. Renaming a chain doesn't break things; changing the sequence
  by even one residue does — regenerate the MSA.
- The `query` row's sequence in `.aligned.pqt` must match the FASTA
  sequence exactly (no gaps).
