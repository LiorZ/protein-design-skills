---
name: fair-esm
description: >
  Run the FAIR `fair-esm` package — the original Meta Fundamental AI Research
  reference implementation of the ESM family of protein language and structure
  models. Use this skill when:
  (1) Extracting per-residue or per-sequence embeddings from a protein
      language model (ESM-2 6 variants from 8M → 15B, ESM-1b, ESM-1v, ESM-MSA),
  (2) Predicting protein 3D structure end-to-end from a single sequence with
      **ESMFold** (`esm-fold` CLI or `model.infer_pdb()`),
  (3) Designing sequences for a fixed backbone — fixed-backbone (a.k.a.
      inverse-folding) sequence design with **ESM-IF1**
      (`GVPTransformer`, single-chain or multi-chain complex),
  (4) Scoring conditional log-likelihoods of candidate sequences against a
      backbone (variant ranking, design scoring, perplexity),
  (5) Zero-shot variant effect prediction on deep mutational scans with
      **ESM-1v** ensembles or ESM-MSA (wt-marginals, masked-marginals,
      pseudo-perplexity),
  (6) Unsupervised contact prediction from attention maps
      (`return_contacts=True` / `predict_contacts`),
  (7) Bulk FASTA → embedding pipelines via `esm-extract`, FSDP CPU-offloading
      for the 15B model, the ESM Metagenomic Atlas (~770M predicted
      structures + embeddings).

  Covers installation (PyPI `fair-esm`, `fair-esm[esmfold]`, conda
  `environment.yml`, OpenFold + `dllogger` requirements, the
  pytorch-geometric dance needed for ESM-IF1), the `esm-fold` and
  `esm-extract` CLIs and every flag, the `esm.pretrained.*` model-zoo
  functions, the `Alphabet` / `BatchConverter` tokenization, the
  `model(tokens, repr_layers=..., return_contacts=...)` forward-pass output
  schema, ESMFold's `infer` / `infer_pdb` / `output_to_pdb` API and
  multimer-via-`:` syntax, `esm.inverse_folding.util` and
  `esm.inverse_folding.multichain_util` (load_structure, load_coords,
  extract_coords_from_complex, sample, sample_sequence_in_complex,
  score_sequence, score_sequence_in_complex, get_encoder_output, partial
  masking of coordinates with `np.inf`), the ESM-1v variant-effect scoring
  strategies, MSA Transformer A3M ingestion, the ESM Atlas API
  (`api.esmatlas.com`), the metadata `parquet`/`sqlite` schema, structural
  split / pre-training split datasets, and known traps (regression weights
  for contacts, `model.eval()` for ESM-IF1, `truncation_seq_length=1022` for
  ESM-2, BOS token, `coords[mask] = np.inf` for partial masking).

  Pairs with: `alphafold` / `chai` / `boltz` (alternative structure
  predictors), `proteinmpnn` / `ligandmpnn` / `solublempnn` (alternative
  inverse-folding sequence design — often higher experimental success rate
  than ESM-IF1), `protein-qc` (filter ESM-PLL / pLDDT / ipTM), `binder-design`
  (campaign tool selection), `foldseek` (search the Atlas), `uniprot` /
  `pdb` (source sequences / structures), `rfdiffusion` / `bindcraft` /
  `boltzgen` (generate backbones to redesign).
license: MIT
category: protein-language-model
tags: [protein-language-model, embeddings, structure-prediction, inverse-folding, variant-effect, contact-prediction, esm2, esmfold, esm-if, esm-1v, msa-transformer, zero-shot, sequence-design, esm-atlas]
repo: https://github.com/facebookresearch/esm
pip: fair-esm
pip_with_esmfold: fair-esm[esmfold]
papers:
  esm2_esmfold: https://www.science.org/doi/abs/10.1126/science.ade2574
  esm1: https://doi.org/10.1073/pnas.2016239118
  esm1v: https://doi.org/10.1101/2021.07.09.450648
  esm_if: https://doi.org/10.1101/2022.04.10.487779
  msa_transformer: https://www.biorxiv.org/content/10.1101/2021.02.12.430858v1
  contacts: https://doi.org/10.1101/2020.12.15.422761
  lm_design: https://doi.org/10.1101/2022.12.21.521521
atlas: https://esmatlas.com
api: https://api.esmatlas.com/foldSequence/v1/pdb/
huggingface: https://huggingface.co/docs/transformers/model_doc/esm
---

# fair-esm — FAIR's ESM / ESM-2 / ESMFold / ESM-IF / ESM-1v Reference Code

## What this is

`fair-esm` (PyPI) / `facebookresearch/esm` (GitHub) is the **reference
PyTorch implementation** of the entire ESM family of protein models from the
Meta Fundamental AI Research Protein Team (FAIR). One pip install gives you
every public model and four CLIs:

| Model family | Best checkpoint to start with | What it does | CLI / API |
|--------------|-------------------------------|--------------|-----------|
| **ESM-2** (PLM) | `esm2_t33_650M_UR50D` (650M) ; scale to `esm2_t36_3B_UR50D` (3B) or `esm2_t48_15B_UR50D` (15B) for top quality | Per-residue / per-sequence embeddings, attention contact maps, masked-LM scoring | `esm-extract` CLI; `model(tokens, repr_layers=[...], return_contacts=True)` |
| **ESMFold** | `esmfold_v1` | End-to-end **single-sequence** 3D structure prediction. ~88 mean pLDDT on the small example sequence. Multimer with `:`-separated chains. | `esm-fold -i in.fasta -o pdb_out`; `model.infer_pdb(seq)` |
| **ESM-IF1** (`GVPTransformer`) | `esm_if1_gvp4_t16_142M_UR50` (124M) | **Inverse folding** / fixed-backbone sequence design from N / CA / C coordinates. 51 % native recovery, 72 % buried. Single-chain or multi-chain complex. Tolerates partially masked backbones (`coords = np.inf`). | `examples/inverse_folding/sample_sequences.py` and `score_log_likelihoods.py`; `model.sample(coords, temperature=T)` |
| **ESM-1v** | `esm1v_t33_650M_UR90S_[1-5]` (5-model ensemble) | Zero-shot variant effect prediction on deep mutational scans. Three scoring strategies: `wt-marginals`, `masked-marginals`, `pseudo-ppl`. | `examples/variant-prediction/predict.py` |
| **MSA Transformer** | `esm_msa1b_t12_100M_UR50S` | Per-residue embeddings + SOTA unsupervised contacts from an A3M multiple-sequence alignment. | `model(tokens)`; pass `--msa-path` to `predict.py` for variants |
| **ESM-1b / ESM-1** | `esm1b_t33_650M_UR50S` | Predecessor PLMs — superseded by ESM-2 for most uses. | Same API as ESM-2 |

> **`fair-esm` is in maintenance mode.** The FAIR team's new code base is
> [`evolutionaryscale/esm`](https://github.com/evolutionaryscale/esm) (ESM-3 /
> ESM-C). For ESM-2 / ESMFold / ESM-IF / ESM-1v this repository is still the
> reference. For ESM-3 use the EvolutionaryScale package instead. Hugging Face's
> `transformers` library also re-implements ESM-1b / ESM-2 / ESMFold with a
> standardized API — see `huggingface.co/docs/transformers/model_doc/esm`.

## When to use which model

Pick the smallest model that meets your accuracy bar — every step up in
parameters costs roughly 4 × the memory and 2-4 × the time.

| Task | First choice | Notes |
|------|--------------|-------|
| One-shot structure prediction | `esmfold_v1` | Single sequence, no MSA. ~1 GPU-second per residue at L≈400 on an A100. For higher accuracy on hard targets, switch to AlphaFold-Multimer / Chai-1 / Boltz-2. |
| Bulk structure prediction (≥ 1 k sequences) | `esm-fold` CLI with `--max-tokens-per-batch` | Sorts by length and batches. Use `--cpu-offload` to fit longer sequences on smaller GPUs. |
| Generic embeddings for ML downstream task | `esm2_t33_650M_UR50D`, `--include mean per_tok` from final layer (33) | 650M is the standard "good default". 15B is rarely worth it for transfer learning. |
| Contact prediction | `esm2_t33_650M_UR50D` + `return_contacts=True`, **or** `esm_msa1b_t12_100M_UR50S` (better if you have an MSA) | Requires regression weights — auto-downloaded for all models *except* ESM-1v and ESM-IF. |
| Inverse folding / fixed-backbone design | `esm_if1_gvp4_t16_142M_UR50` | For higher experimental success, also try ProteinMPNN / SolubleMPNN — see `binder-design`. |
| Zero-shot variant effect | ESM-1v 5-model ensemble + `masked-marginals` | If you have an MSA, the MSA-Transformer + `masked-marginals` is often slightly better. ESM-2 also works well. |
| Search / browse ~770 M predicted metagenomic structures | ESM Metagenomic Atlas (esmatlas.com) | Folded with `esmfold_v0` / `esmfold_v1`. Foldseek API available for structural search. |

## Three-step quick start

### 1) Install

```bash
# Core (ESM-2, ESM-1, ESM-1v, MSA-Transformer, ESM-IF model class)
pip install fair-esm

# With ESMFold (needs python <= 3.9 and CUDA `nvcc` for OpenFold)
pip install "fair-esm[esmfold]"
pip install 'dllogger @ git+https://github.com/NVIDIA/dllogger.git'
pip install 'openfold @ git+https://github.com/aqlaboratory/openfold.git@4b41059694619831a7db195b7e0988fc4ff3a307'
```

ESM-IF1 has its own conda recipe (because `pytorch-geometric` is finicky):

```bash
conda create -n inverse python=3.9
conda activate inverse
conda install pytorch cudatoolkit=11.3 -c pytorch
conda install pyg -c pyg -c conda-forge
pip install biotite fair-esm
```

Full details, including the `environment.yml` recipe and known-good
PyTorch / CUDA / `pyg` combinations, are in `references/installation.md`.

### 2) Smoke test

```python
import torch, esm
model, alphabet = esm.pretrained.esm2_t33_650M_UR50D()
model.eval()
batch_converter = alphabet.get_batch_converter()
_, _, toks = batch_converter([("p1", "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSL")])
with torch.no_grad():
    out = model(toks, repr_layers=[33], return_contacts=True)
print(out["representations"][33].shape)  # (1, L+2, 1280)
print(out["contacts"].shape)              # (1, L, L)
```

The first call downloads `~650 MB` to `~/.cache/torch/hub/checkpoints/`.

### 3) Run something real

Pick one based on what you actually want to do:

| Want | Run |
|------|-----|
| Embeddings for a FASTA | `esm-extract esm2_t33_650M_UR50D seqs.fa out/ --repr_layers 33 --include mean per_tok` |
| Structure for a FASTA  | `esm-fold -i seqs.fa -o pdbs/` |
| Sample 5 designs for chain C of `target.pdb` | `python examples/inverse_folding/sample_sequences.py target.pdb --chain C --num-samples 5 --temperature 1 --outpath out.fasta` |
| Score variant sequences against backbone | `python examples/inverse_folding/score_log_likelihoods.py target.pdb variants.fa --chain C --outpath scores.csv` |
| Label a DMS CSV with predictions | `python examples/variant-prediction/predict.py --model-location esm1v_t33_650M_UR90S_{1..5} --sequence <WT> --dms-input dms.csv --mutation-col mutant --dms-output dms_scored.csv --offset-idx <N> --scoring-strategy masked-marginals` |

## What each reference page covers

- `references/installation.md` — pip vs conda, CUDA / `nvcc` / OpenFold gotchas, the pyg dance for ESM-IF1, where weights cache, offline use.
- `references/models.md` — every checkpoint, params / layers / embed-dim / dataset, regression-weight matrix (contacts), download URLs.
- `references/esm2-embeddings.md` — `esm-extract` CLI, the `--include {mean,per_tok,bos,contacts}` flags, `repr_layers`, the saved `.pt` schema, truncation, batching by `toks_per_batch`.
- `references/esmfold-structure.md` — `esm-fold` CLI, `model.infer_pdb()` / `infer_pdbs()`, multimer syntax (`chain1:chain2`), `set_chunk_size`, `--cpu-offload` FSDP path, output pLDDT / pTM extraction.
- `references/inverse-folding.md` — ESM-IF1 end-to-end: `load_structure` / `load_coords` / `extract_coords_from_complex`, single-chain vs multi-chain, `model.sample`, `score_sequence` / `score_sequence_in_complex`, partial masking with `np.inf`, `get_encoder_output` for structural reps, and the `sample_sequences.py` / `score_log_likelihoods.py` CLIs.
- `references/variant-prediction.md` — ESM-1v 5-model ensemble, `wt-marginals` / `masked-marginals` / `pseudo-ppl` scoring strategies, `--offset-idx`, A3M MSA ingestion for the MSA Transformer, output CSV schema.
- `references/msa-transformer.md` — A3M / FASTA ingestion, `remove_insertions`, the 3-D token tensor shape `(1, N, L)`, tied-row attention contacts.
- `references/contact-prediction.md` — `predict_contacts` / `return_contacts`, regression-weight requirement, MSA-Transformer contacts vs ESM-2 contacts, evaluation idioms.
- `references/atlas.md` — ESM Metagenomic Atlas: `api.esmatlas.com/foldSequence/v1/pdb/`, metadata `parquet` / `sqlite` schema, bulk download with `aria2c` / `s5cmd`, structure search via Foldseek.
- `references/python-api.md` — every public function/class that's safe to import: `esm.pretrained.*`, `esm.Alphabet`, `esm.BatchConverter`, `esm.FastaBatchedDataset`, `esm.inverse_folding.util.*`, `esm.inverse_folding.multichain_util.*`, the ESMFold `.infer` interface.
- `references/troubleshooting.md` — common failure modes: missing regression weights, `truncation_seq_length=1022`, `nvcc` not found, pyg version mismatch, OOM, `model.eval()` for ESM-IF1, AA repetition in ESM-IF samples (`EEEEEE...`).

## What each example does

`examples/` mirrors the official `examples/` plus a few extras:

- `extract_embeddings.py` — minimal ESM-2 forward pass, save mean + per-tok representations.
- `bulk_extract.sh` — `esm-extract` invocation pattern.
- `fold_single.py` — load `esmfold_v1`, fold one sequence, print mean pLDDT, save PDB.
- `fold_bulk.sh` — `esm-fold` invocation for bulk FASTA folding.
- `inverse_fold_sample.py` — load ESM-IF1, sample N sequences for a target chain.
- `inverse_fold_multichain.py` — multi-chain complex sequence design.
- `inverse_fold_score.py` — score a list of variants against a fixed backbone.
- `inverse_fold_partial_mask.py` — mask a span of backbone with `np.inf` and resample only that span.
- `inverse_fold_encoder_output.py` — extract the L×512 structure representation.
- `variant_dms.sh` — full 5-model ensemble DMS scoring command.
- `contact_prediction.py` — extract attention-based contacts from ESM-2.
- `atlas_api.sh` — fold a sequence via the public ESM Atlas API with `curl`.

All examples are short (≤ 60 lines), self-contained, and use the small
`esm2_t6_8M_UR50D` (8 M) checkpoint where possible so they run on CPU in
under a minute.

## Most common traps (read this even if you skim the rest)

1. **`model.eval()` is mandatory** for ESM-IF1 and recommended everywhere else.
   Forgetting it triggers dropout and you get worse samples / scores.
2. **`truncation_seq_length=1022`** is the default for `esm-extract`. ESM-2
   was trained at length ≤ 1024 (BOS + L + EOS) — sequences past 1022 are
   silently truncated unless you raise this flag (memory permitting).
3. **BOS / EOS tokens** wrap every sequence. When indexing the
   `representations[layer]` tensor, residue *i* is at position *i+1*. The
   `extract.py` recipe slices `[1 : truncate_len + 1]` for per-token reps.
4. **Contact prediction needs regression weights** that are downloaded
   automatically — *except* for ESM-1v, ESM-IF, and partially-trained ESM-2
   (`-270K` / `-500K`). On those models `return_contacts=True` does nothing
   useful.
5. **ESM-IF1 partial masking uses `np.inf`**, not `np.nan`. Set
   `coords[i:j, :, :] = np.inf` to mark residues as having "missing backbone".
6. **Multimers in ESMFold** are encoded as a single sequence with `:`
   between chains; the model inserts a length-25 poly-G linker by default
   (`chain_linker="G" * 25`) and offsets residue index by 512
   (`residue_index_offset=512`). Override with the constructor / `.infer()`
   kwargs.
7. **ESM-IF1 sometimes outputs amino-acid repeats** (e.g. `EEEEEEEE`). The
   official README explicitly recommends filtering these from sampled
   designs — don't trust them as-is.
8. **PyG / `torch-scatter` / CUDA mismatch** is by far the most common
   ESM-IF1 install failure — see `references/installation.md` for the
   matrix. The recent commit `636becf` ("guard torch_scatter dependency")
   makes the import lazy so the package itself imports without it, but
   ESM-IF1 sampling will still fail without it.
9. **15B model + single GPU** needs `--cpu-offload` (FSDP) — see
   `examples/esm2_infer_fairscale_fsdp_cpu_offloading.py` in the repo and
   `references/esmfold-structure.md`.
10. **Reproducibility**: ESMFold has random masking inside `.infer`; if you
    need byte-exact reproducibility, seed `torch.manual_seed` *and* pass an
    explicit `masking_pattern`.

## When **not** to use `fair-esm`

- For ESM-3 / ESM-C → use the `evolutionaryscale/esm` package instead.
- For HF-`transformers`-native pipelines (e.g. ESMFold inside a
  `transformers` `Trainer` or `pipeline`) → use the HF re-implementation.
- For higher-accuracy multimer / antibody / protein-ligand structures →
  use AlphaFold-Multimer / Chai-1 / Boltz-2 (see `chai`, `boltz`,
  `alphafold` skills).
- For high-success-rate binder design → ProteinMPNN-family models tend to
  outperform ESM-IF1 on experimental success, despite ESM-IF1's stronger
  in-silico sequence recovery (see `binder-design`).
- For very long sequences (> ~2 k residues) without GPU offloading →
  AlphaFold-Multimer or chunked ESMFold with `--chunk-size 64` / 32 / 16.

## Reading order

If you're new, start with this SKILL.md, then jump straight to the one
reference page that matches your task (`esm2-embeddings.md`,
`esmfold-structure.md`, `inverse-folding.md`, or `variant-prediction.md`).
Skim `troubleshooting.md` *before* you run anything large.
