# Sampling — model versions, batch sizing, MSA, denoisers

## Pick a model

| Checkpoint | Default? | Training data | Params | When |
|-----------|----------|---------------|--------|------|
| `bioemu-v1.0` | no | 161k AFDB structures + 216 ms MD + 19k ΔG measurements | 31.4 M | Reproducing the **preprint** numbers (https://doi.org/10.1101/2024.12.05.626885) |
| `bioemu-v1.1` | **yes** | Same AFDB + MD as v1.0, **502k** ΔG measurements | 31.4 M | The Science paper. Use this for everything unless you have a reason not to. |
| `bioemu-v1.2` | no | AFDB same as v1.0, **145.4 ms** of MD, **1.3M** ΔG measurements, **extra residue-type / residue-pair embeddings** | 35.7 M | Most-recent ΔG predictions; trained on the largest stability dataset. Best when stability prediction is the goal. |

CLI: `--model_name bioemu-v1.2`. Python: `model_name="bioemu-v1.2"`.

Checkpoints download from
`huggingface.co/microsoft/bioemu/checkpoints/<model_name>/` on first
use.

## Batch size (the one knob that fights OOM)

```text
real_batch = max(1, int(batch_size_100 * (100 / L)**2))
```

`batch_size_100` is the batch size **as if** the sequence were 100 aa
long. The real batch then scales **quadratically** down with length:

| `batch_size_100` | L=50 | L=100 | L=200 | L=300 | L=600 |
|------------------:|-----:|------:|------:|------:|------:|
| 20 (the upstream A100-80 GB number) | 80 | 20 | 5 | 2 | 1 |
| 10 (CLI default) | 40 | 10 | 2 | 1 | 1 |
| 5 | 20 | 5 | 1 | 1 | 1 |
| 3 | 12 | 3 | 1 | 1 | 1 |
| 1 | 4 | 1 | 1 | 1 | 1 |

When you OOM, halve `batch_size_100` and retry. The default of 10 is
already conservative; only raise it if you have an A100 or larger.

## Sampling-time budget

From the upstream README, measured on a single A100 80 GB at
`batch_size_100=20`, **1000 samples**:

| Sequence length | Wall-clock |
|----------------:|-----------:|
| 100 | ~4 min |
| 300 | ~40 min |
| 600 | ~150 min |

Wall-clock scales like **time × samples × L²**, so:
- Halving `num_samples` halves wall-clock.
- Doubling L roughly quadruples wall-clock and quadruples per-sample memory.
- Steering with `num_particles=k` multiplies wall-clock by ~k (each
  output sample needs k candidates).

## MSA / embedding pipeline

BioEmu uses the bundled (inlined) ColabFold MSA + AlphaFold2 single +
pair embedding extractor. You don't see this — it just happens before
the first denoising batch.

Three modes:

| Mode | What you pass | What happens |
|------|---------------|--------------|
| **Default** | `sequence="<aa>"` or a FASTA path | A ColabFold MMseqs2 request goes to the public server, MSA is built, AF2 single + pair embeddings are extracted, and the embeddings are cached in `cache_embeds_dir`. |
| **BYO MSA** | `sequence="/path/to/aln.a3m"` | The A3M is parsed (query = first row); AF2 single + pair embeddings are extracted from it directly. `msa_host_url` is ignored. |
| **Custom server** | `sequence="<aa>"` + `msa_host_url="https://your-server/api"` | Same as default but the MSA request goes to your server. |

Embedding cache: by default `~/.cache/colabfold/embeds_cache/`. Hash is
sequence-content based — re-using the same `cache_embeds_dir` across
runs skips the MSA step entirely for sequences already cached.

## Denoisers

Two built-in unsteered denoiser configs ship under
`src/bioemu/config/denoiser/`:

| File | `_target_` | Default `N` | Notes |
|------|------------|-------------|-------|
| `dpm.yaml` | `bioemu.shortcuts.dpm_solver` | 50 | The **default**. Deterministic DPM-Solver. Faster, fewer steps. |
| `heun.yaml` | `bioemu.shortcuts.heun_denoiser` | 100 | Heun-style stochastic denoiser. More steps, more noise (`noise: 0.5`). Slower, sometimes better quality on out-of-distribution sequences. |

Pick with `--denoiser_type dpm` or `--denoiser_type heun`. **Ignored if
`--denoiser_config` is set** — steering YAMLs replace the whole
denoiser.

For most production sampling, **default DPM + physical steering** is
the right choice.

## Output filtering — `filter_samples=True` (default)

After sampling, BioEmu post-filters out:
- Steric clashes (any non-neighbour atom pair too close).
- Chain breaks (Cα–Cα distance way too large between consecutive residues).

For long / disordered chains, this can discard a large fraction of
samples. Two ways to recover:

1. **Best — enable physical steering** (`physical_steering.yaml`). The
   YAML penalizes those exact violations during denoising, so fewer
   samples ever become unphysical, and the post-filter discards far
   fewer.
2. **Diagnostic — `--filter_samples=False`** to keep everything and
   inspect the distribution of clashes / chain breaks.

## Resumability

`output_dir` is **stateful**:

- On entry, BioEmu calls `count_samples_in_output_dir(output_dir)` —
  this counts the existing `batch_*.npz` files' samples.
- It only generates the missing batches to reach `num_samples`.
- `sequence.fasta` is checked: if it exists and disagrees with the
  current sequence, BioEmu errors out (so you don't accidentally mix
  ensembles).

To **extend** an existing ensemble to more samples: keep the same
`output_dir` and raise `num_samples`. To **start fresh** with the
same sequence and a different config: use a new `output_dir`.

To **forget and re-run**: `rm -rf <output_dir>/batch_*.npz <output_dir>/samples.xtc <output_dir>/topology.pdb`.

## Reproducibility

`base_seed` is set to `time.time_ns()` if not provided. Each batch
uses `base_seed + start_idx`. For a fully reproducible ensemble:

```python
sample(sequence='GYDPETGTWG', num_samples=1000, output_dir='~/run1',
       base_seed=42)
sample(sequence='GYDPETGTWG', num_samples=1000, output_dir='~/run2',
       base_seed=42)
# run1/samples.xtc == run2/samples.xtc  (modulo nondeterministic ops)
```

Note: some GPU ops are nondeterministic by default. For bit-exact
reproducibility set `torch.use_deterministic_algorithms(True)` before
calling `sample`, but this can slow sampling significantly.
