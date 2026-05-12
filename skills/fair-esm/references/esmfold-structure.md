# ESMFold — single-sequence 3D structure prediction

ESMFold predicts structure end-to-end from a single sequence — no MSA,
no templates. Internally it's a 3 B-parameter ESM-2 LM (frozen) plus a
~690 M-parameter folding trunk adapted from AlphaFold2.

## When to reach for ESMFold

- You have a single sequence and want a quick structure (10 s – 5 min on
  a 24 GB GPU for L ≤ 500).
- You're folding lots (10 k+) of sequences and don't have MSA infra.
- You're scoring designs in a loop and need a fast oracle.

When to **not** use ESMFold:

- Higher-accuracy single structures → AlphaFold2 / AlphaFold-Multimer.
- High-quality multimers / antibody / protein-ligand → Chai-1 / Boltz-2.
- Cases where you'd benefit from an MSA → AF2 / Boltz / Chai.

## The `esm-fold` CLI

After `pip install "fair-esm[esmfold]"`, the `esm-fold` command lands on
PATH.

```
esm-fold -i <fasta> -o <pdb_dir> \
  [--num-recycles 4] \
  [--max-tokens-per-batch 1024] \
  [--chunk-size <int|None>] \
  [--cpu-only] [--cpu-offload] \
  [-m, --model-dir <PARENT_OF_HUB_CACHE>]
```

| Flag | Default | Notes |
|------|---------|-------|
| `-i / --fasta` | required | Multi-record FASTA. Multimers: chains separated by `:` in a single record. |
| `-o / --pdb`   | required | Output dir, one `<header>.pdb` per record. Created if missing. |
| `-m / --model-dir` | None | Sets `torch.hub.set_dir(...)` so `~/.cache/torch/hub` points to a different parent. Useful for offline / shared caches. |
| `--num-recycles`   | trunk default (4) | More recycles = better structures, more time. |
| `--max-tokens-per-batch` | 1024 | Groups short sequences. Set to 0 to disable batching. |
| `--chunk-size`     | None  | Axial attention chunking. Recommended 128 / 64 / 32 when OOM on long sequences. |
| `--cpu-only`       | False | Use CPU. Trunk runs in fp32. Slow. |
| `--cpu-offload`    | False | FSDP-offload the ESM-2 LM to CPU RAM — lets you fold longer sequences on a small GPU. Single-GPU only; uses `torch.distributed`. |

Output PDBs contain pLDDT in the B-factor column. Mean pLDDT is logged at
runtime.

### Recipes

```bash
# 100 monomers from a FASTA
esm-fold -i monomers.fa -o pdbs/

# Long sequences on a 24 GB GPU
esm-fold -i long.fa -o pdbs/ --chunk-size 64

# Very long / very small GPU
esm-fold -i long.fa -o pdbs/ --chunk-size 32 --cpu-offload

# Multimer (chains separated by ':')
cat <<EOF > complex.fa
>my_complex
MKTVRQERLKSIVRILERSKEPVS...:KALTARQQEVFDLIRDHISQ...
EOF
esm-fold -i complex.fa -o pdbs/

# CPU-only (slow, debug only)
esm-fold -i tiny.fa -o pdbs/ --cpu-only
```

### Reading mean pLDDT from output

```python
import biotite.structure.io as bsio
struct = bsio.load_structure("pdbs/my_seq.pdb", extra_fields=["b_factor"])
print(struct.b_factor.mean())   # = mean pLDDT
```

## Python API: `model.infer_pdb()`

```python
import torch, esm

model = esm.pretrained.esmfold_v1()      # downloads ~10 GB to ~/.cache
model = model.eval().cuda()

# Optional memory knob — axial attention chunking
# model.set_chunk_size(128)

pdb_str = model.infer_pdb("MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSL")

with open("result.pdb", "w") as f:
    f.write(pdb_str)
```

### `infer_pdb` vs `infer_pdbs` vs `infer`

| Method | Input | Output |
|--------|-------|--------|
| `model.infer_pdb(seq, **kw)`  | `str`     | `str` (PDB) |
| `model.infer_pdbs(seqs, **kw)`| `List[str]` | `List[str]` |
| `model.infer(seqs, **kw)`     | `str` or `List[str]` | dict of tensors |

The full `.infer(...)` signature:

```python
out = model.infer(
    sequences,                      # str or List[str], chains joined by ':'
    residx=None,                    # explicit residue indices (else contiguous)
    masking_pattern=None,           # binary (B, L) tensor of positions to mask
    num_recycles=None,              # default 4
    residue_index_offset=512,       # gap between chains in a multimer
    chain_linker="G" * 25,          # 25-G linker between chains
)
# out keys: "positions", "atom37_atom_exists", "plddt", "ptm",
#           "mean_plddt", "chain_index", ...
```

`output_to_pdb(out) -> List[str]` converts the tensor output into per-sample
PDB strings.

### Multimer semantics

A multimer is a single sequence with `:` separators (e.g.
`"AAA...:BBB...:CCC..."`). On the inside, ESMFold:

1. Strips the `:` separators.
2. Builds a `chain_index` tensor labelling each residue with its chain.
3. Inserts an offset of `residue_index_offset` (default 512) into the
   `residx` between chains so the positional embedding "sees" a gap.
4. Optionally concatenates a poly-G `chain_linker` between chains so the
   structure module produces a single contiguous backbone, then masks
   the linker out of the final structure with `linker_mask`.

To pass no linker (rare): `chain_linker=""`.

## Memory & timing

ESMFold scales worse than ESM-2 because the folding trunk is `O(L^2)` in
both memory and time, and recycles multiply by `num_recycles + 1`. Rough
guide on an A100 (80 GB):

| Length | `num_recycles=4`, no chunking | Notes |
|--------|-------------------------------|-------|
| 200    | ~2 s                          | Trivial |
| 500    | ~10 s                         | Comfortable |
| 1000   | ~60 s                         | Use `chunk_size=64` if GPU < 40 GB |
| 1500   | ~3 min                        | `chunk_size=32` recommended |
| 2000+  | OOM without `--cpu-offload`   | Plus pTM accuracy degrades |

`--cpu-offload` (FSDP) trades GPU memory for time and won't reduce wall
clock — only enables longer sequences on a small GPU.

## ESMFold output schema

```python
out = model.infer(["MKTV..."])
out["plddt"].shape                # (B, L, 37) — per-residue, per-atom pLDDT
out["mean_plddt"].shape           # (B,)
out["ptm"].shape                  # (B,)
out["positions"].shape            # (8, B, L, 14, 3)  — 8 recycle samples × 14-atom representation
out["atom37_atom_exists"].shape   # (B, L, 37) — which atom-37 atoms are real
```

When `output_to_pdb` writes the final PDB, pLDDT is written into the
B-factor column (averaged over heavy atoms).

## ESM Atlas API (no install needed)

If you only need a single structure occasionally, the public ESM Atlas
API is the simplest path:

```bash
curl -X POST --data "MKTVRQERLKSIVRILERSKEPVS..." \
  https://api.esmatlas.com/foldSequence/v1/pdb/ > result.pdb
```

Limits: ~400 residues per call; rate-limited per IP; no multimer
support. For anything else, run locally.

## Reproducibility

`infer` doesn't take a seed kwarg. To reproduce a run byte-for-byte:

```python
import torch
torch.manual_seed(0)
torch.use_deterministic_algorithms(True)
out1 = model.infer_pdb(seq)
torch.manual_seed(0)
out2 = model.infer_pdb(seq)
assert out1 == out2
```

Some kernels are nondeterministic on GPU; if exact reproducibility
matters, fix seeds **and** disable nondeterministic CUDA kernels via
`torch.use_deterministic_algorithms`.
