# MSAs

Boltz uses multiple-sequence alignments (MSAs) for protein chains only. Nucleic acids and ligands do not have MSAs. There are four ways to provide them.

## 1. Auto-generated via ColabFold (`--use_msa_server`)

Easiest. Boltz queries `https://api.colabfold.com` (ColabFold MMseqs2) for every protein chain that does **not** have an explicit `msa:` field.

```bash
boltz predict input.yaml --use_msa_server
```

For multimers, the server is queried per chain; pairing across chains is then done locally according to `--msa_pairing_strategy`:

- `greedy` (default) — fast, pair the best hits per taxon.
- `complete` — exhaustive pairing; slower.

Results are cached inside `boltz_results_<stem>/processed/msa/` so subsequent runs with the same input reuse them.

## 2. Local `.a3m` per chain

```yaml
sequences:
  - protein:
      id: A
      sequence: MVTPEGNVSLVD...
      msa: ./examples/msa/seq1.a3m
```

Format is standard A3M: the first sequence must be the query (matching `sequence` in the YAML), subsequent sequences are aligned hits. `gz`-compressed inputs are not auto-decoded; pre-extract to `.a3m`.

Generate your own MSAs with `colabfold_search`, `hhblits`, `jackhmmer`, or a local ColabFold instance — see `https://github.com/YoshitakaMo/localcolabfold`.

If you mix local and server MSAs, chains with `msa:` use the file; chains without go to the server (when `--use_msa_server` is set).

## 3. Paired CSV for multimers

If your multimer chains need to be **co-aligned** (paired by taxonomy or by an interaction signal), provide a CSV per chain with two columns:

```csv
sequence,key
MVTPEG...,uniref_42
MVTPDG...,uniref_43
...
```

Sequences with the same `key` across the CSVs of different chains are treated as a paired row.

```yaml
sequences:
  - protein:
      id: A
      sequence: ...
      msa: ./msa_A.csv
  - protein:
      id: B
      sequence: ...
      msa: ./msa_B.csv
```

Use this when you have a curated pairing (e.g. species-matched orthologs); otherwise rely on the server-side pairing.

## 4. Single-sequence mode (`msa: empty`)

Skip the MSA entirely:

```yaml
- protein:
    id: A
    sequence: MVTPEG...
    msa: empty
```

**This degrades accuracy significantly** for natural proteins — Boltz, like AF, was trained with MSAs. Reasonable use cases:

- De novo designed sequences with no natural homologs (the MSA would be noise anyway).
- Sanity checks / smoke tests.
- Comparing models when you want to ablate the MSA channel.

For most other cases, `--use_msa_server` is what you want.

## Authentication for `--use_msa_server`

If your endpoint (custom ColabFold or proxied service) requires auth, Boltz supports two schemes; **only one** at a time.

### Basic auth

CLI:

```bash
boltz predict ... --use_msa_server \
  --msa_server_url https://my-colabfold.example.com \
  --msa_server_username me \
  --msa_server_password secret
```

Env (recommended for password):

```bash
export BOLTZ_MSA_USERNAME=me
export BOLTZ_MSA_PASSWORD=secret
boltz predict ... --use_msa_server --msa_server_url https://my-colabfold.example.com
```

### API key

CLI:

```bash
boltz predict ... --use_msa_server \
  --msa_server_url https://my-colabfold.example.com \
  --api_key_header X-API-Key \
  --api_key_value <token>
```

Env (recommended for the secret):

```bash
export MSA_API_KEY_VALUE=<token>
boltz predict ... --use_msa_server \
  --msa_server_url https://my-colabfold.example.com \
  --api_key_header X-API-Key
```

Some gateways use a non-default header name (e.g. `X-Gravitee-Api-Key`) — set `--api_key_header` accordingly.

Mixing basic auth and API key in the same call raises an error.

## Tuning MSA depth

Two flags:

- `--max_msa_seqs N` — hard cap on rows after loading (default 8192). Deeper MSAs cost more VRAM.
- `--subsample_msa` + `--num_subsampled_msa N` — randomly subsample at runtime (default subsample size 1024). Subsampling is useful for ensembling or for low-VRAM cards.

For most production runs the defaults are fine. Drop to `--num_subsampled_msa 512` to fit large complexes on a 24 GB card.

## Caching

Auto-generated MSAs are written to `boltz_results_<stem>/processed/msa/<sha256(seq)>.a3m`. Reusing the same YAML in the same `--out_dir` reuses the cache; deleting `processed/msa/` (or passing `--override`) forces re-fetch.

If you maintain a shared MSA directory across many runs, point your YAMLs' `msa:` field directly at the cached `.a3m` files — that avoids server hits entirely.
