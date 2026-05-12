# ESM-1v — zero-shot variant effect prediction

ESM-1v is a 5-model ensemble of 650 M-parameter ESM-1 variants trained
on UR90/S. It produces SOTA *zero-shot* predictions of mutational
effects from a single wild-type sequence — no labelled training data
required.

Paper: Meier et al. 2021,
https://doi.org/10.1101/2021.07.09.450648

ESM-2 also works well for this task; the official scripts let you swap
the model location freely.

## The `predict.py` script

```
python examples/variant-prediction/predict.py \
  --model-location <MODEL_1> [<MODEL_2> ...] \
  --sequence <WT_SEQUENCE> \
  --dms-input <DMS.csv> \
  --mutation-col <COL_NAME> \
  --dms-output <DMS_LABELED.csv> \
  --offset-idx <FIRST_RESIDUE_NUMBER> \
  --scoring-strategy {wt-marginals,masked-marginals,pseudo-ppl} \
  [--msa-path <A3M_FILE>]  [--msa-samples 400] \
  [--nogpu]
```

Args:

- `--model-location` — one or more pretrained-model names or local `.pt`
  paths. The classic ESM-1v ensemble is the five
  `esm1v_t33_650M_UR90S_1` … `_5`. Pass all five for the published
  ensemble.
- `--sequence` — the wild-type single-letter amino-acid sequence.
- `--dms-input` — a CSV with one row per variant. Required column is
  `--mutation-col`, formatted as `A24P` (WT-aa, 1-based index, MUT-aa)
  or with `:`-delimited multi-mutations like `A24P:G30L`.
- `--mutation-col` — column name (default `mutant`).
- `--dms-output` — output CSV; the script appends one column per model
  with the variant score.
- `--offset-idx` — the **integer at which position 1 in the mutant code
  corresponds to position 0 of `--sequence`**. For BLAT_ECOLX in the
  paper, `--offset-idx 24` because their numbering starts at residue 24.
- `--scoring-strategy` — see below.
- `--msa-path` / `--msa-samples` — only used with the MSA Transformer.

## Scoring strategies

Define *the score of a single point mutation A→B at position i* as a
log-likelihood-ratio:

```
score = log P(B | context_at_i) - log P(A | context_at_i)
```

The three strategies differ in what "context" means:

### 1. `wt-marginals` (fastest)

Run **one** forward pass on the wild-type sequence. Use the logits at
position *i* directly:

```
score = log p_θ(B | s_wt) - log p_θ(A | s_wt)
```

Cost: 1 forward pass per model in the ensemble. Quality: decent.

### 2. `masked-marginals` (recommended)

For each mutated position *i*, mask the wild-type residue and re-run the
forward pass to score both A and B from the masked context:

```
s_masked = s_wt[:i] + <mask> + s_wt[i+1:]
score = log p_θ(B | s_masked) - log p_θ(A | s_masked)
```

Cost: L forward passes per model (= L × 5 for full ensemble), still
parallelizable. Quality: typically the best of the three on DMS
benchmarks. **Only strategy that works with the MSA Transformer.**

### 3. `pseudo-ppl` (slowest, multi-mutation aware)

For each variant (which may contain multiple mutations), mutate the
sequence first, then compute pseudo-perplexity over the full sequence
(mask each position in turn, sum log-probs):

```
ppl_variant = - sum_{j=1..L-1} log p_θ(s_variant_j | mask_j(s_variant))
```

Cost: L × L (mask each position, score every variant). Quality: best
for variants with multiple mutations because it accounts for the
joint distribution. Slow.

## MSA Transformer variant

Pass `--model-location esm_msa1b_t12_100M_UR50S --scoring-strategy
masked-marginals --msa-path <a3m>`. The MSA Transformer takes its
context from the MSA rather than the masked-LM context.

The script's `read_msa()` helper reads the first `--msa-samples` rows
from an `.a3m` file via `Bio.SeqIO`, automatically stripping insertion
columns. Note that this function assumes A3M format — feed it a3m, not
arbitrary FASTA.

## Output schema

The script writes back the input DMS CSV with one **extra column per
model**, whose values are the log-likelihood ratios for each variant.
You ensemble these by averaging:

```python
import pandas as pd
df = pd.read_csv("dms_labeled.csv")
ensemble_cols = [c for c in df.columns if c.startswith("esm1v_t33_650M_UR90S_")]
df["esm1v_ensemble"] = df[ensemble_cols].mean(axis=1)
```

To compute Spearman rank correlation against an experimental column:

```python
from scipy.stats import spearmanr
rho, _ = spearmanr(df["dms_score"], df["esm1v_ensemble"])
```

## Recipes

### BLAT_ECOLX (paper example)

```bash
python predict.py \
  --model-location esm1v_t33_650M_UR90S_1 esm1v_t33_650M_UR90S_2 \
                   esm1v_t33_650M_UR90S_3 esm1v_t33_650M_UR90S_4 \
                   esm1v_t33_650M_UR90S_5 \
  --sequence HPETLVKVKDAEDQLGARVGYIELDLNSGKILESFRPEERFPMMSTFKVLLCGAVLSRVDAGQEQLGRRIHYSQNDLVEYSPVTEKHLTDGMTVRELCSAAITMSDNTAANLLLTTIGGPKELTAFLHNMGDHVTRLDRWEPELNEAIPNDERDTTMPAAMATTLRKLLTGELLTLASRQQLIDWMEADKVAGPLLRSALPAGWFIADKSGAGERGSRGIIAALGPDGKPSRIVVIYTTGSQATMDERNRQIAEIGASLIKHW \
  --dms-input ./data/BLAT_ECOLX_Ranganathan2015.csv \
  --mutation-col mutant \
  --dms-output ./data/BLAT_ECOLX_Ranganathan2015_labeled.csv \
  --offset-idx 24 \
  --scoring-strategy masked-marginals
```

### Drop-in ESM-2 replacement

```bash
python predict.py \
  --model-location esm2_t33_650M_UR50D \
  --sequence MKTVRQERLKSIVRILER... \
  --dms-input variants.csv \
  --mutation-col mutant \
  --dms-output scored.csv \
  --offset-idx 1 \
  --scoring-strategy masked-marginals
```

### Inverse-folding variant scoring (structure-conditioned)

If you have a structure, use ESM-IF1 instead — `score_log_likelihoods.py`
in `examples/inverse_folding/`. ESM-IF1 leverages backbone information and
typically outperforms sequence-only models on DMS benchmarks of structured
proteins.

## Mutation-string parsing

The variants column accepts `<WT><pos><MUT>` codes:

- `A24P` — substitute the residue at position 24 from A to P
- `A24P:G30L` — two mutations (`:`-delimited)

Positions are 1-based, offset by `--offset-idx`. The script
asserts `sequence[pos - offset_idx] == wt_aa`; if that fails, your
offset is wrong or your sequence doesn't match the DMS scan.

## Aggregated paper results

`data/raw_df.csv`, `rho_pp`, and `aggregated_rho` files are released
from the paper at:

- https://dl.fbaipublicfiles.com/fair-esm/examples/variant-prediction/data/raw_df.csv

These hold per-mutation scores from many baselines (ESM-1v, ESM-MSA-1b,
EVE, DeepSequence, …) across the 41 DMS datasets used in the paper.
