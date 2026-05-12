# ESM-IF1 — inverse folding (fixed-backbone sequence design)

ESM-IF1 (a.k.a. `GVPTransformer`, Hsu et al. 2022) predicts protein
**sequences** from **backbone coordinates**. Use it for fixed-backbone
sequence design, mutational effect scoring conditioned on structure, or
to get a learned representation of a backbone.

Trained on 12 M AlphaFold2-predicted UR50 structures plus CATH 4.3. The
model achieves **51 %** native sequence recovery on held-out backbones,
**72 %** on buried residues. Tolerates partial masking of backbone
coordinates so you can design only specific regions.

The official scripts are in
`examples/inverse_folding/{sample_sequences,score_log_likelihoods}.py`.
Both wrap the same Python API.

## Loading the model

```python
import torch, esm, esm.inverse_folding

model, alphabet = esm.pretrained.esm_if1_gvp4_t16_142M_UR50()
model = model.eval()                # MANDATORY — dropout otherwise
if torch.cuda.is_available():
    model = model.cuda()
```

`esm.inverse_folding` exposes two utility submodules:

- `esm.inverse_folding.util` — single-chain helpers
- `esm.inverse_folding.multichain_util` — multi-chain (complex) helpers

## Backbone coordinate format

The model consumes an `(L, 3, 3)` float array of N / CA / C coordinates:

| Axis | Meaning |
|------|---------|
| 0    | residue index `i` (0 … L-1) |
| 1    | atom index — `0` = N, `1` = CA, `2` = C |
| 2    | x / y / z |

Missing residues / unresolved regions → set
`coords[i, :, :] = float("inf")`. The model was trained with span
masking and tolerates partial masking gracefully.

Use `float("inf")`, not `float("nan")`. `float("nan")` is reserved for
truly unparseable residues from the PDB loader.

## Loading a structure

### Single chain

```python
import esm.inverse_folding
coords, native_seq = esm.inverse_folding.util.load_coords(
    "target.pdb",   # .pdb or .cif
    "C",            # chain id
)
# coords: (L, 3, 3)  ; native_seq: str length L
```

### Multi-chain complex

```python
structure = esm.inverse_folding.util.load_structure(
    "target.pdb",
    chain=["A", "B", "C", "D"],
)
coords, native_seqs = esm.inverse_folding.multichain_util.extract_coords_from_complex(structure)
# coords      : Dict[chain_id, (L_chain, 3, 3)]
# native_seqs : Dict[chain_id, str]
```

Pass `chain=None` to `load_structure` to load all chains.

## Sampling sequences

### Single-chain backbone

```python
sampled_seq = model.sample(coords, temperature=1.0)
```

- `temperature=1.0` is the default — good diversity, ~51 % recovery on
  natural backbones.
- `temperature=1e-6` ≈ greedy decoding → highest recovery, lowest
  diversity. Use this when you want a "best guess".
- Realistic recipe: sample many at `T=1.0`, then filter (see below).

### Multi-chain complex

```python
target_chain_id = "C"
sampled_seq = esm.inverse_folding.multichain_util.sample_sequence_in_complex(
    model, coords, target_chain_id, temperature=1.0, padding_length=10,
)
```

Internally, the encoder sees the full complex (all chains concatenated
with 10 `np.nan`-padded "gap" residues between them, target chain
first); the decoder samples only `len(coords[target_chain_id])` residues.

**Single-chain vs multi-chain — try both.** The paper shows multi-chain
context typically reduces perplexity and improves recovery, but on some
targets the single-chain mode is better. There's no rule of thumb.

## Scoring sequences

### Single chain

```python
ll_fullseq, ll_withcoord = esm.inverse_folding.util.score_sequence(
    model, alphabet, coords, seq
)
# Both are floats. Average log-likelihood per residue.
# ll_fullseq  : averaged over all residues
# ll_withcoord: averaged only over residues with finite coordinates
```

`perplexity = exp(-ll_fullseq)`. Lower perplexity → better fit between
sequence and backbone.

### Multi-chain

```python
ll_fullseq, ll_withcoord = esm.inverse_folding.multichain_util.score_sequence_in_complex(
    model, alphabet, coords, target_chain_id, target_seq
)
```

## Encoder output as a structure representation

```python
rep = esm.inverse_folding.util.get_encoder_output(model, alphabet, coords)
# rep.shape == (L, 512)
```

The encoder is the GVP-graph stack — pure geometry, no sequence
information. The 512-d vector per residue is a useful structural
embedding for downstream tasks (clustering, similarity, regression).

For complexes:

```python
rep_target = esm.inverse_folding.multichain_util.get_encoder_output_for_complex(
    model, alphabet, coords, target_chain_id
)
# rep_target.shape == (L_target, 512) — sliced to the target chain only
```

## Partial backbone masking

ESM-IF1 was trained with span masking — you can mask any subset of
residues by setting their coordinates to `inf`:

```python
import numpy as np
from copy import deepcopy

masked_coords = deepcopy(coords)
masked_coords[:15] = np.inf          # mask first 15 residues
ll, ll_wc = esm.inverse_folding.util.score_sequence(model, alphabet, masked_coords, seq)
```

Sampling from a partially-masked backbone designs the masked region only
in the *probabilistic* sense — the model's decoder is autoregressive
across the whole length and can still generate any letter at any
position. There's no built-in "design only positions X..Y" knob; the
common pattern is:

1. Sample full-length sequences from the masked backbone.
2. Keep only the residues at positions you intended to design; splice
   them back into the wild-type sequence.

For more rigorous "constrained design" you'd use the
`partial_seq` argument to `model.sample` (used internally by the
multichain helper) — a list of length L of either letter codes / special
tokens (e.g. `<pad>`, `<mask>`) that fix the corresponding output
position. The multichain helper sets `<pad>` for non-target chains and
`<mask>` for target-chain positions.

## CLI: `sample_sequences.py`

```
python examples/inverse_folding/sample_sequences.py <pdbfile> \
  --chain <CHAIN_ID> \
  [--temperature 1.0] \
  [--num-samples 1] \
  [--outpath output/sampled_seqs.fasta] \
  [--multichain-backbone | --singlechain-backbone] \
  [--nogpu]
```

Sequence recovery against the native sequence is printed for each
sample.

**Important known failure mode:** ESM-IF1 sometimes emits long homopolymer
runs (`EEEEEEEE`, `KKKKKKK`, `AAAAAA`). The official README explicitly
flags this and recommends filtering them. A simple sanity check:

```python
import re
def has_long_repeat(seq, n=5):
    return bool(re.search(r"(.)\1{%d,}" % (n - 1), seq))
```

## CLI: `score_log_likelihoods.py`

```
python examples/inverse_folding/score_log_likelihoods.py <pdbfile> <seqfile.fa> \
  --chain <CHAIN_ID> \
  --outpath output/scores.csv \
  [--multichain-backbone | --singlechain-backbone] \
  [--nogpu]
```

Outputs a CSV with columns `seqid,log_likelihood`. Use this to rank
variant sequences against a fixed backbone.

## Typical campaign recipes

### "Redesign chain C of this PDB while keeping the rest"

```python
coords, native_seqs = esm.inverse_folding.multichain_util.load_complex_coords(
    "target.pdb", chains=["A", "B", "C", "D"]
)
designs = []
for _ in range(100):
    seq = esm.inverse_folding.multichain_util.sample_sequence_in_complex(
        model, coords, "C", temperature=1.0
    )
    designs.append(seq)
# Then score each design against the same backbone:
scored = []
for seq in designs:
    ll, _ = esm.inverse_folding.multichain_util.score_sequence_in_complex(
        model, alphabet, coords, "C", seq
    )
    scored.append((seq, ll))
scored.sort(key=lambda x: -x[1])    # higher LL = better
```

### "Score variant effects on a known structure"

```python
ll_native, _ = esm.inverse_folding.util.score_sequence(model, alphabet, coords, native_seq)
for variant_seq in variant_list:
    ll, _ = esm.inverse_folding.util.score_sequence(model, alphabet, coords, variant_seq)
    delta_ll = ll - ll_native       # positive = better-than-native fit
```

### "Score a single point mutation"

```python
i, mut = 42, "V"                     # mutate position 42 to V
variant_seq = native_seq[:i] + mut + native_seq[i+1:]
ll_variant, _ = esm.inverse_folding.util.score_sequence(model, alphabet, coords, variant_seq)
```

## Comparison to ProteinMPNN / SolubleMPNN / LigandMPNN

ESM-IF1 was the first big inverse-folding LM and is still strong in
recovery benchmarks. But for **experimental success rates** on
de-novo-designed binders, ProteinMPNN-family models often do better. As
of 2026:

| Tool           | Best for | Trade-off |
|----------------|----------|-----------|
| ESM-IF1        | High in-silico recovery; partial masking; tolerates noisy backbones | Tends to repeat amino acids; no ligand awareness |
| ProteinMPNN    | Field-default for fixed-backbone design; high experimental hit rates | Backbone-only; no built-in masking with `inf` |
| SolubleMPNN    | Bias designs toward solubility | Smaller community |
| LigandMPNN     | Aware of ligand context | Need to provide ligand atoms |

Consider running ESM-IF1 and ProteinMPNN as complementary samplers and
filtering the union — see the `binder-design` skill.

## What `examples/inverse_folding/` ships

```
data/         5YH2.pdb + a small set of mutated sequences
notebook.ipynb / notebook_multichain.ipynb       walkthrough
sample_sequences.py                              sampling CLI
score_log_likelihoods.py                         scoring  CLI
output/                                          example outputs
```

The CATH 4.3 backbone-coordinates and split files used by Hsu et al. are
at:

- https://dl.fbaipublicfiles.com/fair-esm/data/cath4.3_topologysplit_202206/chain_set.jsonl
- https://dl.fbaipublicfiles.com/fair-esm/data/cath4.3_topologysplit_202206/splits.json
