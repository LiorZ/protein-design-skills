# ESM-2 — embeddings, masked LM, attention contacts

This page covers everything you need to drive the ESM-2 family
(`esm.pretrained.esm2_*`) — both the `esm-extract` CLI and the in-process
Python API.

## The `esm-extract` CLI

After `pip install fair-esm` the command `esm-extract` lands on PATH. It
is the bulk-FASTA → embeddings pipeline.

```
esm-extract \
  <model_location> <fasta_file> <output_dir> \
  --repr_layers <layer_indices...> \
  --include {mean,per_tok,bos,contacts}+ \
  [--toks_per_batch 4096] \
  [--truncation_seq_length 1022] \
  [--nogpu]
```

Positional args:

- `model_location` — name of a pretrained model (e.g.
  `esm2_t33_650M_UR50D`) **or** a local `.pt` path. Local files must have
  the matching `-contact-regression.pt` next to them if you use
  `--include contacts`.
- `fasta_file` — input FASTA. Sequences past `--truncation_seq_length`
  are silently truncated.
- `output_dir` — created if missing. One `.pt` per FASTA entry; filename
  is the FASTA header (label) with `.pt` suffix.

Flags:

| Flag | Default | Notes |
|------|---------|-------|
| `--repr_layers` | `[-1]` (final) | List of integers. Use negative indices for last-N (e.g. `-1` = final). Validated against `model.num_layers`. The 650 M model has layers 0..33; 0 = embedding-only, 33 = post-final-transformer. |
| `--include`     | required       | One or more of `mean`, `per_tok`, `bos`, `contacts`. |
| `--toks_per_batch` | 4096        | Sum of tokens (residues) per GPU forward pass. Drop to 1024 / 512 on small GPUs. |
| `--truncation_seq_length` | 1022 | ESM-2 training length was 1024 tokens including BOS/EOS. |
| `--nogpu`       | False          | Force CPU even if CUDA is present. |

> The official docs warn: **don't use `--include bos`** with the public
> pretrained models. They were trained without BOS-token supervision, so
> the BOS-embedding has no semantic meaning. It's exposed only because
> ESM-1 used a different recipe.

### What lands in each output `.pt`

`torch.load(out_dir/<label>.pt)` returns a dict:

| Key | When present | Shape | Notes |
|-----|--------------|-------|-------|
| `label`              | always               | `str` | FASTA header (description-stripped) |
| `representations[L]` | with `per_tok`       | `(seq_len, embed_dim)` | Per-residue, BOS/EOS stripped (slice `[1 : seq_len+1]`) |
| `mean_representations[L]` | with `mean`     | `(embed_dim,)` | Mean over residues only (excludes BOS/EOS) |
| `bos_representations[L]`  | with `bos`      | `(embed_dim,)` | Position 0 = BOS |
| `contacts`           | with `contacts`      | `(L, L)`     | Symmetric contact-probability matrix |

`L` keys are the integers passed to `--repr_layers`.

### Idioms

```bash
# Mean + per-token from the final layer of the 650 M model:
esm-extract esm2_t33_650M_UR50D seqs.fa out/ \
  --repr_layers 33 --include mean per_tok

# Multiple layers (e.g. for probing different depths):
esm-extract esm2_t33_650M_UR50D seqs.fa out/ \
  --repr_layers 0 16 33 --include mean

# Attention-based contacts:
esm-extract esm2_t33_650M_UR50D seqs.fa out/ \
  --repr_layers 33 --include contacts

# Tiny smoke test (8 M model, CPU):
esm-extract esm2_t6_8M_UR50D seqs.fa out/ \
  --repr_layers 6 --include mean --nogpu
```

## Python forward pass

```python
import torch, esm

model, alphabet = esm.pretrained.esm2_t33_650M_UR50D()
model = model.eval()                     # disable dropout
batch_converter = alphabet.get_batch_converter()

data = [
    ("p1", "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSL"),
    ("p2", "KALTARQQEVFDLIRDHISQTGMPPTRAEIAQRLGFRSPNAAEEH"),
    ("p2_mask", "KALTARQQEVFDLIRD<mask>ISQTGMPPTRAEIAQRLGFRSPNAAEEH"),
]
labels, strs, tokens = batch_converter(data)
# tokens.shape == (3, max_L + 2). Padded with alphabet.padding_idx.

with torch.no_grad():
    out = model(tokens, repr_layers=[33], return_contacts=True)

# out["logits"]            : (B, L+2, vocab=33)  — masked-LM logits
# out["representations"][33]: (B, L+2, 1280)
# out["contacts"]          : (B, L, L)           — already BOS/EOS-stripped
# out["attentions"]        : (B, layers, heads, L+2, L+2)  if you set need_head_weights=True
```

### Indexing past BOS

When extracting per-token reps, residue *i* in the input string lives at
position *i+1*. Standard slice:

```python
seq_len = (tokens != alphabet.padding_idx).sum(1)  # per-sequence length
reps = out["representations"][33]
for i, L in enumerate(seq_len):
    per_residue = reps[i, 1 : L - 1]      # drop BOS at 0 and EOS at L-1
    sequence_rep = per_residue.mean(0)    # (1280,)
```

### Masked-LM scoring (point mutations)

The forward pass returns logits over the 33-token alphabet for every
position. To score a mutation, take the log-softmax and subtract the WT
logprob from the mutant logprob:

```python
logp = torch.log_softmax(out["logits"], dim=-1)        # (B, L+2, vocab)
wt_id  = alphabet.get_idx("A")
mut_id = alphabet.get_idx("V")
delta_logp = logp[0, 1 + i, mut_id] - logp[0, 1 + i, wt_id]
```

The `wt-marginals` strategy uses logits from a **single, unmasked**
forward pass. `masked-marginals` masks position *i* explicitly and
re-runs the forward pass per position — more accurate, ~L × slower. See
`variant-prediction.md` for the full recipe.

## Batching with `FastaBatchedDataset`

```python
from esm import FastaBatchedDataset
ds = FastaBatchedDataset.from_file("seqs.fa")
batches = ds.get_batch_indices(toks_per_batch=4096, extra_toks_per_seq=1)
loader = torch.utils.data.DataLoader(
    ds, collate_fn=alphabet.get_batch_converter(1022), batch_sampler=batches
)
for labels, strs, toks in loader:
    ...
```

`FastaBatchedDataset` sorts by length so each batch is roughly square,
which minimizes padding waste. `extra_toks_per_seq=1` accounts for the
EOS token (BOS is implicit in the converter).

## Memory rules of thumb

Forward-pass GPU memory roughly scales as `B × L × hidden + B × L^2 × heads`.
Drop `--toks_per_batch` when you hit OOM. Long-sequence inference is
quadratic in memory; truncate or use `--cpu-offload` for the 15 B model.

| Model | Recommended `toks_per_batch` on 24 GB | On 80 GB |
|-------|--------------------------------------:|---------:|
| 8 M   | 16 384                                | 65 536   |
| 35 M  | 8 192                                 | 32 768   |
| 150 M | 4 096                                 | 16 384   |
| 650 M | 2 048                                 | 8 192    |
| 3 B   | 512                                   | 2 048    |
| 15 B  | OOM without `--cpu-offload`           | 256      |

(These are heuristics from typical use, not a benchmark.)
