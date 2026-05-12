# Driving `fair-esm` from Python

This page lists the **public surface** of the `esm` package — the parts
that have been stable across the recent releases and are safe to depend
on. Internal helpers exist but move between versions.

## Top-level imports

```python
import esm
esm.__version__

# Re-exported at the top level:
esm.Alphabet
esm.BatchConverter
esm.FastaBatchedDataset
esm.ProteinBertModel
esm.ESM2
esm.MSATransformer
esm.pretrained                       # submodule with all model factories
```

## Loading models

Every checkpoint is a function on `esm.pretrained` that returns a
`(model, alphabet)` tuple:

```python
model, alphabet = esm.pretrained.esm2_t33_650M_UR50D()
```

Generic loaders:

```python
from esm.pretrained import (
    load_model_and_alphabet,           # smart dispatcher (name or .pt path)
    load_model_and_alphabet_hub,       # force hub download
    load_model_and_alphabet_local,     # force local .pt
)
```

`load_model_and_alphabet("/path/to/x.pt")` will also load
`/path/to/x-contact-regression.pt` next to it if the checkpoint needs
one.

## Tokenization

```python
alphabet              = esm.Alphabet.from_architecture("ESM-1b")  # rare, usually obtained from pretrained()
batch_converter       = alphabet.get_batch_converter(truncation_seq_length=1022)

labels, strs, tokens  = batch_converter([
    ("p1", "MKTV..."),
    ("p2", "KALT..."),
])
# tokens.shape == (B, max_L + 2)   ; padded with alphabet.padding_idx
# tokens[:, 0]   = BOS
# tokens[:, L+1] = EOS

alphabet.padding_idx
alphabet.mask_idx
alphabet.cls_idx
alphabet.eos_idx
alphabet.standard_toks   # ['L','A','G','V',...]
alphabet.get_idx("V")
```

The MSA Transformer's `batch_converter` accepts a different schema —
`List[List[Tuple[label, seq]]]` where each inner list is one MSA.

## ESM-2 / ESM-1 / ESM-1v / ESM-1b forward pass

```python
out = model(tokens, repr_layers=[33], return_contacts=True,
            need_head_weights=False)

out["logits"]                  # (B, L+2, vocab)
out["representations"][33]     # (B, L+2, hidden)  per requested layer
out["contacts"]                # (B, L, L)    if return_contacts and regression weights exist
out["attentions"]              # (B, layers, heads, L+2, L+2)  if need_head_weights
```

`model.num_layers` tells you the valid range for `repr_layers`. Index 0
is the embedding output (pre-transformer); index `num_layers` is the
final layer.

`model.predict_contacts(tokens)` is a convenience that wraps the contact
prediction without the dict overhead.

## ESMFold forward pass

```python
model = esm.pretrained.esmfold_v1().eval().cuda()
model.set_chunk_size(64)                 # optional memory knob

pdb = model.infer_pdb(seq)                # str -> str
pdbs = model.infer_pdbs([seq1, seq2])     # List -> List

out = model.infer(
    seqs,                                 # str | List[str], chains ':'-joined
    residx=None,
    masking_pattern=None,
    num_recycles=None,
    residue_index_offset=512,
    chain_linker="G" * 25,
)
# Important keys:
# out["positions"]        : (8, B, L, 14, 3)  — 8 recycle snapshots
# out["plddt"]            : (B, L, 37)
# out["mean_plddt"]       : (B,)
# out["ptm"]              : (B,)
# out["chain_index"]      : (B, L)
# out["atom37_atom_exists"]: (B, L, 37)

pdbs = model.output_to_pdb(out)           # List[str]
```

## Inverse folding API

```python
import esm.inverse_folding as inv
import esm.inverse_folding.util as inv_u
import esm.inverse_folding.multichain_util as inv_m

# --- single chain ---
structure = inv_u.load_structure("target.pdb", chain="C")
coords, native_seq = inv_u.extract_coords_from_structure(structure)
# or one-liner:
coords, native_seq = inv_u.load_coords("target.pdb", "C")

sampled_seq = model.sample(coords, temperature=1.0, device=torch.device("cuda"))

ll_full, ll_with_coord = inv_u.score_sequence(model, alphabet, coords, seq)

rep = inv_u.get_encoder_output(model, alphabet, coords)   # (L, 512)

# --- multi-chain ---
structure   = inv_u.load_structure("target.pdb", chain=["A","B","C","D"])
coords, native_seqs = inv_m.extract_coords_from_complex(structure)
# or:
coords, native_seqs = inv_m.load_complex_coords("target.pdb", ["A","B","C","D"])

seq_C = inv_m.sample_sequence_in_complex(model, coords, "C", temperature=1.0)
ll_full, ll_wc = inv_m.score_sequence_in_complex(model, alphabet, coords, "C", seq_C)
rep_C = inv_m.get_encoder_output_for_complex(model, alphabet, coords, "C")
```

`model.sample(coords, partial_seq=None, temperature=1.0, device=None)`
takes:

- `coords` : `(L, 3, 3)` numpy array. Use `np.inf` for masked residues.
- `partial_seq` : optional `List[str]` of length L. Each element is an
  amino-acid letter (constrain) or a special token (`<pad>` to ignore
  that position in decoding, `<mask>` to design it).
- `temperature` : softmax temperature. `1e-6` ≈ greedy.

## FASTA dataset helper

```python
from esm import FastaBatchedDataset
ds = FastaBatchedDataset.from_file("seqs.fa")        # parses fasta
batches = ds.get_batch_indices(toks_per_batch=4096, extra_toks_per_seq=1)
loader = torch.utils.data.DataLoader(
    ds,
    collate_fn=alphabet.get_batch_converter(truncation_seq_length=1022),
    batch_sampler=batches,
)
for labels, strs, tokens in loader:
    ...
```

## torch.hub one-liner

```python
import torch
model, alphabet = torch.hub.load("facebookresearch/esm:main", "esm2_t33_650M_UR50D")
```

Bypasses the `pip install fair-esm` step — useful in sandboxed
notebooks. Note: ESM-IF1 via hub still needs `pytorch-geometric` and
`torch-scatter` locally.

## Common subprocess wrappers

For batch CLI invocation from Python, the simplest pattern is
`subprocess.run`:

```python
import subprocess, pathlib

def esm_extract(model_name, fasta, out_dir, layers=(33,), include=("mean", "per_tok")):
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    cmd = ["esm-extract", model_name, str(fasta), str(out_dir),
           "--repr_layers", *[str(l) for l in layers],
           "--include", *include]
    subprocess.run(cmd, check=True)

def esm_fold(fasta, out_dir, *, chunk_size=None, cpu_offload=False):
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    cmd = ["esm-fold", "-i", str(fasta), "-o", str(out_dir)]
    if chunk_size: cmd += ["--chunk-size", str(chunk_size)]
    if cpu_offload: cmd += ["--cpu-offload"]
    subprocess.run(cmd, check=True)
```

These wrap the two stable CLIs. Output files have documented schemas;
parse them after.

## Loading a saved embedding dict

```python
import torch
emb = torch.load("out/p1.pt", map_location="cpu")
emb["label"]                          # 'p1'
emb["mean_representations"][33]       # (1280,)
emb["representations"][33]            # (L, 1280)        — if --include per_tok
emb["contacts"]                       # (L, L)           — if --include contacts
```
