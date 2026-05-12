# ESM Metagenomic Atlas

The [ESM Metagenomic Atlas](https://esmatlas.com) is a public repository
of **~770 M** predicted protein structures, folded with `esmfold_v0` /
`esmfold_v1` from sequences in the MGnify protein database.

| Version | Released | Source DB | ESMFold version |
|---------|----------|-----------|-----------------|
| `v0`         | Nov 2022 | MGnify90 2022_05 | `esmfold_v0` |
| `v2023_02`   | Mar 2023 | MGnify90 2023_02 | `esmfold_v1` |

Bulk-download docs: https://github.com/facebookresearch/esm/tree/main/scripts/atlas

## Public APIs

### 1. Fold a single sequence (no install needed)

```bash
curl -X POST --data "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG" \
  https://api.esmatlas.com/foldSequence/v1/pdb/ > result.pdb
```

Limits:

- Maximum ~400 residues per call (longer requests reject).
- Per-IP rate limiting; bursting trips a 429.
- Single chain only (no `:`-separated multimer).
- Returns a single PDB string.

Wrap in a `requests` call if needed:

```python
import requests
seq = "MKTVRQERLKSIVRILER..."
r = requests.post("https://api.esmatlas.com/foldSequence/v1/pdb/", data=seq)
r.raise_for_status()
with open("result.pdb", "w") as f:
    f.write(r.text)
```

### 2. Sequence search

`https://esmatlas.com/resources?action=search_sequence` — UI-driven
sequence search via BLAST against the Atlas sequence index.

### 3. Structure search (Foldseek)

`https://search.foldseek.com/search` — Foldseek-backed structure search.
Foldseek can search the full Atlas at scale; the public search server
runs without a length cap.

## Bulk download

The full database is provided as PDB files in tarball "bins" grouped by
pTM × pLDDT. URL list files for `aria2c`:

```
aria2c --dir=./download --input-file=urls.txt
```

The **high-confidence** subset (pTM > 0.7 and pLDDT > 0.7, ~1 TB) is
usually what you actually want. The full database is ~15 TB and largely
contains low-confidence predictions.

Embeddings (ESM-2 `t33_650M_UR50D` mean representations) are also
provided as bulk downloads for `v2023_02`.

## Metadata

`metadata.parquet` (~16 GB) / `metadata.sqlite` (~25 GB) hold the
following columns:

| Column           | Meaning |
|------------------|---------|
| `id`             | MGnify ID |
| `ptm`            | pTM score |
| `plddt`          | mean pLDDT |
| `num_conf`       | residues with pLDDT > 0.7 |
| `len`            | length |
| `is_fragment`    | flagged as fragment in MGnify90 |
| `sequenceChecksum` | CRC64 hash of sequence |
| `esmfold_version` | 0 or 1 |
| `atlas_version`   | first Atlas version this prediction appeared in |
| `sequence_dbs`    | comma-separated source MGnify releases |

```python
import pandas as pd
df = pd.read_parquet("metadata.parquet")
df = df[~df.plddt.isna()]            # drop length>1280, unpredicted
df_hi = df.query("ptm > 0.7 and plddt > 0.7")
```

Sequences longer than 1280 residues were not folded — those rows have
NaN structure metadata.

## Related: download scripts

`scripts/atlas/{v0,v2023_02}/` in the upstream repo contain `bins.txt`
files enumerating the structure tarballs. Use those with `aria2c` or
`s5cmd` (S3) — the README explicitly recommends those over `wget`.

## Use cases this enables

- Search for natural homologs of a designed protein.
- Foldseek a designed binder backbone against ~770 M structures to spot
  proximate natural folds (potentially scaffold inspiration or red
  flags).
- Bulk download a confidence-filtered subset for training your own
  model.
- Cross-reference an MGnify sequence against its predicted structure
  via the `sequenceChecksum` (CRC64 of the canonical sequence).
