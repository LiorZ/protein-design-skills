# Unsupervised contact prediction from attention maps

Both ESM-2 and the MSA Transformer expose unsupervised contact
predictors. The method: a logistic regression over symmetrized,
APC-corrected attention maps. The regression weights are released as
separate `*-contact-regression.pt` files per model.

Paper: Rao et al. 2020,
https://doi.org/10.1101/2020.12.15.422761

## Which models have it

Auto-downloaded with the main weights for **every** checkpoint **except**:

- ESM-1v (`esm1v_*`)
- ESM-IF (`esm_if*`)
- Partially-trained ESM-2 (`*_270K` / `*_500K`)

For those models, `return_contacts=True` returns tensors that aren't
calibrated; ignore them.

## How to call it

### Direct method on the model

```python
import esm, torch
model, alphabet = esm.pretrained.esm2_t33_650M_UR50D()
model = model.eval().cuda()
batch_converter = alphabet.get_batch_converter()

_, _, tokens = batch_converter([("p", "MKTVRQERLKSIVRILER...")])
with torch.no_grad():
    contacts = model.predict_contacts(tokens.cuda())
# contacts.shape == (1, L, L)   — BOS / EOS already stripped
```

### Via the generic forward pass

```python
with torch.no_grad():
    out = model(tokens.cuda(), return_contacts=True)
contacts = out["contacts"]   # (B, L, L)
```

This is the same predictor; convenience either way.

### From the CLI

```bash
esm-extract esm2_t33_650M_UR50D seqs.fa out/ \
  --repr_layers 33 --include contacts
```

`torch.load("out/<header>.pt")["contacts"]` gives the `(L, L)` matrix.

## Output semantics

Each entry `contacts[i, j]` is a **predicted contact probability** in
`[0, 1]`. The convention from the paper:

- Two residues are in contact if `min over heavy-atom pairs ‖x_i − x_j‖ ≤ 8 Å`
  and they are at least 6 sequence positions apart.
- Prediction quality is usually reported as P@L / P@L/2 / P@L/5 (top
  predictions for short/medium/long-range contacts).

## Evaluation idioms

```python
import torch

def top_k_precision(pred, gold, k):
    """pred, gold are (L, L); gold is binary contact mask."""
    L = pred.shape[0]
    iu = torch.triu_indices(L, L, offset=6)        # long-range only
    p, g = pred[iu[0], iu[1]], gold[iu[0], iu[1]]
    top = p.topk(k).indices
    return g[top].float().mean().item()

# P @ L
print(top_k_precision(contacts[0], gold_contacts, k=L))
# P @ L/2, L/5
print(top_k_precision(contacts[0], gold_contacts, k=L // 2))
print(top_k_precision(contacts[0], gold_contacts, k=L // 5))
```

## MSA Transformer contacts

MSA Transformer contacts are state-of-the-art when you have a good MSA:

```python
import esm
model, alphabet = esm.pretrained.esm_msa1b_t12_100M_UR50S()
model = model.eval().cuda()
bc = alphabet.get_batch_converter()
_, _, tokens = bc([msa])      # msa = List[Tuple[label, seq]] from a3m
with torch.no_grad():
    contacts = model.predict_contacts(tokens.cuda())
```

Quality scales with MSA depth — 64 / 128 / 256 random rows is the
useful range.

## Visualizing

```python
import matplotlib.pyplot as plt
plt.imshow(contacts[0].cpu().numpy(), origin="lower")
plt.colorbar(label="contact probability")
plt.savefig("contacts.png", dpi=200)
```

For a side-by-side with the true contact map (if you have a structure),
draw `gold` in the lower triangle and `pred` in the upper triangle.

## What about contacts without regression weights?

The model output `out["attentions"]` is a `(B, layers, heads, L+2, L+2)`
tensor of raw attention maps. You *can* train your own regression on top
(this is roughly what the paper did to produce the canonical predictor),
but for standard use just use the auto-downloaded regression.

## Related: distogram from ESMFold

If you ran ESMFold, the `out["distogram_logits"]` field of the inference
output is a `(B, L, L, 64)` distogram over the 64 standard bins. That's
not strictly "contacts" but is a richer view of pairwise geometry.
