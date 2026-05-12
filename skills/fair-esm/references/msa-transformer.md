# MSA Transformer

`esm_msa1b_t12_100M_UR50S` is a 100 M-parameter transformer that
operates over **MSAs** rather than single sequences. It uses tied-row
attention to share information across the columns of an alignment.

Paper: Rao et al. 2021,
https://www.biorxiv.org/content/10.1101/2021.02.12.430858v1

## When to use

- Variant effect prediction with an MSA — see `variant-prediction.md`.
- Unsupervised contact prediction when you have an MSA (best results
  in the ESM family).
- Per-residue embeddings that incorporate alignment context.

For pure single-sequence tasks, use ESM-2 instead.

## Input format

Token tensor shape is `(B, N, L)`:

| Axis | Meaning |
|------|---------|
| 0 | batch |
| 1 | sequences in the MSA (N rows; row 0 is the query) |
| 2 | residues (L columns; BOS at column 0) |

Practically, pass a `List[List[Tuple[str, str]]]` to `BatchConverter` —
one outer list element per batch item, each containing the MSA rows.

```python
import esm
model, alphabet = esm.pretrained.esm_msa1b_t12_100M_UR50S()
model = model.eval()
batch_converter = alphabet.get_batch_converter()

msa = [
    ("query",   "MKTV-RQE..."),
    ("homolog1","MKTLLRQE..."),
    ("homolog2","-KTVRRQE..."),
    # ...
]
labels, strs, tokens = batch_converter([msa])
# tokens.shape == (1, len(msa), L+1)  — BOS prepended
```

## Loading A3M files

A3M is the standard alignment format used by HHblits, ColabFold, etc.

- **Lowercase columns are insertions** relative to the query.
- `.` and `*` are also markers to strip.

The official `predict.py` provides:

```python
import string
from Bio import SeqIO
import itertools

def remove_insertions(seq: str) -> str:
    deletekeys = dict.fromkeys(string.ascii_lowercase)
    deletekeys["."] = None
    deletekeys["*"] = None
    return seq.translate(str.maketrans(deletekeys))

def read_msa(filename: str, nseq: int):
    return [
        (rec.description, remove_insertions(str(rec.seq)))
        for rec in itertools.islice(SeqIO.parse(filename, "fasta"), nseq)
    ]
```

A3M files are valid FASTA, so `SeqIO.parse(filename, "fasta")` works.

## MSA depth

The model was trained with `N` up to 128 rows. Typical practice:

- 128 random rows → robust contact prediction
- 256 rows → maybe a bit better, more memory
- 1 row → MSA Transformer collapses to a poor single-sequence LM —
  don't bother

## Forward pass

```python
with torch.no_grad():
    out = model(tokens.cuda(), repr_layers=[12], need_head_weights=True, return_contacts=True)

out["representations"][12].shape   # (B, N, L+1, 768)
out["contacts"].shape              # (B, L, L)        — query-vs-query
out["row_attentions"].shape        # (B, L_layers, H, N, N, L, L)  if requested
```

The query-conditioned per-residue embedding is `out["representations"][12][:, 0, 1:]`.

## Limitations

- `MSATransformer` raises `ValueError` in `esm-extract` — that script
  doesn't handle MSA inputs. Run your own loop using
  `FastaBatchedDataset` or simply iterate manually.
- Memory scales with `N × L` and `L^2` — long-and-deep MSAs OOM fast.
  256 rows × 500 columns is a comfortable ceiling on a 24 GB GPU.

## Compared to AF2 / Boltz / Chai MSAs

The MSA Transformer is much smaller than AF2's Evoformer and is
intended as a generic representation learner, not a structure
predictor. If you want structures from an MSA, use AlphaFold2 / Boltz /
Chai-1 (the `chai` / `boltz` / `alphafold` skills).
