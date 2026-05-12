# Unconditional protein generation

DISCO can generate protein sequences + 3D structures **without any
conditioning target**, which is useful for:

- Benchmarking the model against other unconditional generators
  (Genie3, RFdiffusion+ProteinMPNN+AF2).
- Building a library of de novo backbones to seed downstream design.
- Stress-testing your pipeline before adding ligand / nucleic-acid
  conditioning.

## Built-in unconditional config

`input_jsons/unconditional_config.json` contains four fully masked
protein chains at lengths **70, 100, 200, 300** — the canonical
unconditional evaluation set in the paper.

```bash
# Paper-quality, 100 seeds per length:
python runner/inference.py \
  experiment=designable \
  effort=max \
  input_json_path=input_jsons/unconditional_config.json \
  seeds=\[$(seq -s "," 0 99)\]
```

For prototyping, `effort=fast` is the right call — the paper explicitly
allows it for unconditional generation:

```bash
python runner/inference.py \
  experiment=designable \
  effort=fast \
  input_json_path=input_jsons/unconditional_config.json \
  seeds=\[0,1,2,3,4\]
```

## Custom length sweeps

A length sweep is just a JSON file with one job per length:

```json
[
  {"name": "len_50",  "sequences": [{"proteinChain": {"sequence": "<50 hyphens>",  "count": 1}}]},
  {"name": "len_100", "sequences": [{"proteinChain": {"sequence": "<100 hyphens>", "count": 1}}]},
  {"name": "len_150", "sequences": [{"proteinChain": {"sequence": "<150 hyphens>", "count": 1}}]},
  {"name": "len_200", "sequences": [{"proteinChain": {"sequence": "<200 hyphens>", "count": 1}}]},
  {"name": "len_300", "sequences": [{"proteinChain": {"sequence": "<300 hyphens>", "count": 1}}]},
  {"name": "len_400", "sequences": [{"proteinChain": {"sequence": "<400 hyphens>", "count": 1}}]}
]
```

(See [`examples/unconditional_sweep.json`](../examples/unconditional_sweep.json)
for a ready-to-edit file.)

Practical limits:

- **70–300 residues** — the paper's canonical range. Predictable behaviour.
- **300–500 residues** — works but increases GPU memory super-linearly.
  Use an A100/H100/L40S; bring CUTLASS / EvoformerAttention.
- **>500 residues** — possible but you'll likely OOM without 80GB GPUs.

## Length-vs-quality

The paper finds that co-designability **decreases gently with length**
in the unconditional setting — long proteins are harder to refold
correctly. Sample more seeds at the long end to compensate.

| Length | Recommended seeds | Effort |
|-------:|------------------:|:------:|
| 50–100 | 20–50 | `fast` |
| 100–200 | 50–100 | `fast` or `max` |
| 200–300 | 100+ | `max` |
| 300+ | 200+ | `max` |

## Output

Same layout as conditional generation (see [outputs.md](outputs.md)):

```
output/
├── pdbs/
│   ├── length_70_sample_0.pdb
│   ├── length_100_sample_0.pdb
│   └── ...
└── sequences/
    ├── length_70_sample_0.txt
    └── ...
```

No `_ligands.txt` files. No DNA / RNA annotation lines.

## Common downstream uses

1. **Refold check** with ESMFold or AF2 (faster than Chai-1 for monomers
   you only care about backbone-of). See `esm` and `alphafold` skills.
2. **Diversity clustering** to deduplicate the library. See `foldseek`.
3. **MPNN sequence resampling** on top of the DISCO backbones if you
   want more sequence variety per fold. See `proteinmpnn`,
   `solublempnn`, or `ligandmpnn`.
4. **Biophysical QC** with the `protein-qc` skill before any wet-lab
   pickup.

## Tips

- **`experiment=designable` is the right default** for unconditional
  generation — that's where co-designability is highest.
- **`effort=fast` is fine** here (paper allows). For very long proteins
  (>250 residues), bump to `max` because the long-tail penalty grows.
- **`n_seq_duplicates_per_structure=N`** to sample multiple sequence
  draws per backbone — cheap way to get a sequence ensemble.
- **`num_inference_seeds=N`** is a shortcut for `seeds=[0..N-1]`. Use
  it when you don't need specific seed control.
