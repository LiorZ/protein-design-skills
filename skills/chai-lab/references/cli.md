# CLI reference

`chai-lab` is a Typer app with four subcommands:

| Subcommand        | What it does |
|-------------------|--------------|
| `fold`            | Run inference on a single FASTA file |
| `fold-batch`      | Run inference on every FASTA in a directory, parallel across GPUs |
| `a3m-to-pqt`      | Convert `.a3m` MSA files in a directory to Chai's `.aligned.pqt` format |
| `citation`        | Print BibTeX |

`chai-lab --help` lists them; each subcommand has its own `--help`.

## `chai-lab fold`

Signature (call as `chai-lab fold FASTA_FILE OUTPUT_DIR [OPTIONS]`):

```
fasta_file               Path to FASTA-like input
output_dir               Output directory (must be empty / non-existent)
--use-esm-embeddings / --no-use-esm-embeddings
                          Include ESM-2 sequence embeddings (default: True)
--use-msa-server / --no-use-msa-server
                          Query ColabFold MMseqs2 (default: False)
--msa-server-url URL      Override MSA server URL
                          (default: https://api.colabfold.com)
--msa-directory PATH      Local directory of `<hash>.aligned.pqt` files
                          (mutually exclusive with --use-msa-server)
--constraint-path PATH    Restraints CSV (contact / pocket / covalent)
--use-templates-server / --no-use-templates-server
                          Pull structural templates from ColabFold
                          (requires --use-msa-server) (default: False)
--template-hits-path PATH Local `.m8` template-hits file
                          (mutually exclusive with --use-templates-server)
--recycle-msa-subsample N Subsample MSA each recycle (default: 0 = off)
--num-trunk-recycles N    Trunk recycle count (default: 3)
--num-diffn-timesteps N   Diffusion timesteps (default: 200)
--num-diffn-samples N     Diffusion samples per trunk run (default: 5)
--num-trunk-samples N     Independent trunk seeds (default: 1)
--seed INT                Random seed (default: None)
--device STRING           cuda:N (default: cuda:0)
--low-memory / --no-low-memory
                          Keep activations on CPU between stages
                          (default: True; turn off for speed if you have VRAM)
--fasta-names-as-cif-chains / --no-fasta-names-as-cif-chains
                          Use entity `name=` as CIF chain ID
                          (default: False; CIF chains auto-assigned A,B,C…)
```

### Common recipes

Single-sequence fold (fastest, lower accuracy):

```bash
chai-lab fold input.fasta out/
```

With MSAs + templates (recommended for real complexes):

```bash
chai-lab fold --use-msa-server --use-templates-server input.fasta out/
```

With local MSAs:

```bash
chai-lab fold --msa-directory ./msas/ input.fasta out/
```

With restraints:

```bash
chai-lab fold --constraint-path contacts.csv input.fasta out/
```

Increase sampling for harder targets:

```bash
chai-lab fold --num-trunk-samples 3 --num-diffn-samples 5 --seed 0 input.fasta out/
# → 3 × 5 = 15 candidates
```

Self-hosted ColabFold server:

```bash
chai-lab fold --use-msa-server \
              --msa-server-url https://api.internal.colab/ \
              input.fasta out/
```

## `chai-lab fold-batch`

Signature: `chai-lab fold-batch INPUT_DIR --output-dir OUTPUT_DIR [OPTIONS]`.

```
input_dir                 Directory containing .fasta / .fa files
                          (non-recursive)
--output-dir PATH         Base output dir; one subdir per FASTA
--devices STRING          Comma-separated GPU indices, e.g. "0,1,3"
                          (default: all visible CUDA devices)
... (all `fold` flags above pass through) ...
```

Spawns one worker process per device with `multiprocessing` `spawn`
context. Each worker processes FASTAs from a shared queue. Returns a
list of `BatchResult` dataclasses (`fasta_file`, `output_dir`,
`success`, `error_message`). Failures are logged but do not abort other
workers.

Output layout:

```
output_dir/
  <fasta_stem_1>/
    pred.model_idx_0.cif … pred.model_idx_4.cif
    scores.model_idx_0.npz … scores.model_idx_4.npz
    msas/ (optional)
  <fasta_stem_2>/
    …
```

See [batch.md](batch.md) for the Python entrypoint and patterns for
running 1000+ designs.

## `chai-lab a3m-to-pqt`

Converts a directory of `.a3m` files (one query, many alignments) into
Chai's `.aligned.pqt` format. The resulting file's name is the sequence
hash that Chai uses to look up MSAs at fold time. See [msas.md](msas.md)
for the schema.

```bash
chai-lab a3m-to-pqt ./a3ms/   # writes <hash>.aligned.pqt files in place
```

The default pairing-key extraction uses UniProt species annotations.
For custom pairing keys (e.g. organism, OrthoDB cluster ID), build
`.aligned.pqt` files manually with
`chai_lab.data.parsing.msas.aligned_pqt.merge_multi_a3m_to_aligned_dataframe`.

## `chai-lab citation`

Prints the BibTeX entry for the technical report. Use this when writing
up results.
