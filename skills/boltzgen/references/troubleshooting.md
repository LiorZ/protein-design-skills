# Troubleshooting

## "My binder hits the wrong site"

By far the most common bug. Cause is almost always one of:

1. **You used author residue IDs**, not the canonical mmCIF
   `label_seq_id`. BoltzGen always uses `label_seq_id`. Open the CIF
   in https://molstar.org/viewer/, hover over a residue, look at the
   *bottom-right* of the screen — the value labeled
   `label_seq_id` is the right one.
2. **You forgot to `boltzgen check`**. The `check` command emits a
   colored CIF showing the binding-site residues. Always run it before
   launching a 60k-design campaign.
3. **`binding_types` was specified but `structure_groups` is
   `visibility: 0`** for those residues. The model can't bind to a region
   whose structure you've hidden. Either restore visibility 1 or pick a
   different anchor region.

## "OOM / CUDA out of memory"

Possible causes, in rough order:

| Likely cause                              | Mitigation                                                                                 |
|-------------------------------------------|--------------------------------------------------------------------------------------------|
| Target is huge (≥ 600 aa)                 | Use `include_proximity` to crop around the binding site (radius 25-40 Å).                  |
| Too many ligands / cofactors imported     | `exclude` cofactors you don't care about, or use `include_proximity` to bound it.           |
| `--diffusion_batch_size` too large        | Drop it to 1 (or to a fraction of `--num_designs`).                                         |
| `folding`/`design_folding` heavy          | Use `--config folding diffusion_samples=3` (default is 5) and/or `recycling_steps=1`.       |
| Old GPU + kernels mismatch                | `--use_kernels false` — slower but more memory-stable.                                      |
| Cuequivariance crashes mid-step           | `--use_kernels false` (capability < 8 NVIDIA cards).                                        |

If only the folding step OOMs but design + IF work, run them separately:

```bash
boltzgen run spec.yaml --output OUT --steps design inverse_folding --num_designs N
boltzgen run spec.yaml --output OUT --steps folding analysis filtering \
  --config folding trainer.devices=1 diffusion_samples=3
```

## "First run hangs / fails on weight download"

```
ConnectionError: Could not download from huggingface.co/boltzgen/...
```

Cause: network policy, full disk, expired DNS, etc.

Fixes:
- Pre-fetch on a node with reliable Internet:
  `boltzgen download all --cache /scratch/$USER/bg_cache`
  then move the cache to the offline node.
- Set `HF_HOME` to a disk with enough room (need ~6 GB).
- Behind a corporate proxy: set `HTTPS_PROXY`, `HTTP_PROXY` and
  optionally `HF_HUB_ENABLE_HF_TRANSFER=1`.
- For authenticated mirrors: `--models_token hf_…`.

## "`cuequivariance` import error"

```
ImportError: libcuequivariance_ops_torch_cu12.so: cannot open shared object file
```

The cuEquivariance kernels need CUDA 12.x. Either fix the CUDA
toolchain or sidestep the kernels:

```bash
boltzgen run ... --use_kernels false
```

If you see it specifically on GPUs older than A100 (capability < 8):
the kernels are auto-disabled by `--use_kernels auto`, so this means
you forced them on. Drop the `--use_kernels true` flag.

## "Pipeline complete, but every design failed filtering"

Three knobs to relax, in order:

1. `--refolding_rmsd_threshold` — default is whatever the protocol set
   (2.0 for peptide, higher for protein). Try `--refolding_rmsd_threshold 3.0`.
2. `--filter_biased false` — disables ALA/GLY/GLU/LEU/VAL composition caps.
3. `--metrics_override k=none` — disable specific failing metrics one at a time.

Use `--steps filtering` so this iterates in seconds, not hours.

If still nothing survives, **check the analysis CSV directly**:

```bash
python -c "
import pandas as pd
df = pd.read_csv('OUT/intermediate_designs_inverse_folded/aggregate_metrics_analyze.csv')
print(df.describe().T)
"
```

If `iptm.max() < 0.4` the diffusion model didn't dock — your spec
probably under-constrains the binder or the target is too large /
flexible. Add explicit `binding:` residues, narrow `include_proximity`,
or supply secondary-structure hints.

## "Designs come back all the same length"

You set `sequence: 80..140` but every design is length 119 (say).

Cause: `--diffusion_batch_size` is too large relative to `--num_designs`.
Length is sampled **once per batch**, so with batch=10 and 10 designs
total all share one length.

Fixes:
- Drop `--diffusion_batch_size 1` (slowest, perfectly balanced).
- Raise `--num_designs` to many multiples of the batch size.

## "I want cysteines for my peptide but inverse folding refuses to add them"

Default for peptide / antibody / nanobody is `--inverse_fold_avoid C`.
Override it:

```bash
boltzgen run spec.yaml --protocol peptide-anything \
  --inverse_fold_avoid ""
```

(empty string = nothing avoided)

You also need to *want* a Cys at that position — typically you'd add
explicit `C` letters in the sequence and a `bond:` constraint for the
disulfide, rather than relying on IF to spontaneously place one.

## "`--steps filtering` complains about missing metrics"

```
KeyError: 'plip_hbonds_refolded' not in metrics CSV
```

The analysis step didn't run far enough. Either:

- The `folding` or `design_folding` step didn't complete (rerun with
  `--reuse`).
- You're filtering an output dir from an old BoltzGen version with a
  different metrics column set. Delete `aggregate_metrics_analyze.csv`
  and rerun `--steps analysis filtering`.

## "Bond constraint says atom not found"

```
ValueError: atom CK not in residue WHL #1
```

Atom names are CCD-standard for ligands, case-sensitive. Look up the
CCD entry at https://www.rcsb.org/ligand/<CCD> and use its exact atom
names. For SMILES ligands the name is element + 1-based SMILES order
(`C6` = sixth carbon in the SMILES).

## "Designed peptide is twisted / weird / non-canonical at the cyclic junction"

For head-to-tail cyclization use `cyclic: true` on the `protein` entity.
For more exotic cyclization (e.g., side-chain–N or side-chain–side-chain)
use `bond:` constraints + `leaving_atoms:`.

If a junction looks geometrically impossible, you may have:
- Indices counted from the *minimum* length (correct — but easy to slip on).
- Used the wrong atom name (`OE1` vs `OE2`).
- Forgotten to declare the matching `leaving_atoms:` for a side-chain
  ester / amide.

## "Output is huge and disk fills up"

`intermediate_designs/` plus `intermediate_designs_inverse_folded/refold_cif/`
dominate. Keep both if you might want to refilter or re-fold; otherwise
after the campaign is done you can keep only `final_ranked_designs/` and
the CSV + PDF.

```bash
# Safe slim-down: remove the heavy intermediates after final filtering
rm -rf OUT/intermediate_designs OUT/intermediate_designs_inverse_folded/{*.cif,*.npz,refold_design_cif}
# Keep refold_cif/ and metrics CSVs so refiltering still works
```

## "`boltzgen check` shows nothing or crashes"

- Confirm the YAML path is correct and the embedded `path: ...` is
  resolvable relative to the YAML.
- Confirm chain IDs match what's in the CIF.
- The moldir is required even for `check` — first run will download it.
- The output CIF *is* written to `OUT/<spec_stem>.cif`; if you forgot
  `--output DIR`, you'll only get the stdout validation message.

## "`boltzgen merge` errors on overlapping IDs"

It shouldn't — merge renames colliding design IDs. If you see this,
you're probably running an older version. `pip install -U boltzgen` and
try again.

## "`--reuse` re-generates everything anyway"

Two common causes:

1. The hash inputs changed (different `--protocol`, `--design_checkpoints`,
   `--step_scale`, etc.). The cache key includes these.
2. You re-ran with a different YAML — the design IDs are derived from
   the spec.

If you want to genuinely top up an existing run, pass identical flags
plus `--reuse`.

## "Wandb is logging when I don't want it to"

Training uses wandb if installed. Set `WANDB_MODE=offline` or
`WANDB_DISABLED=true` in your environment for training. Inference does
not use wandb.

## "The model designed a binder that clashes / has a bad H-bond network"

Inspect `refold_cif/` (not `intermediate_designs/`) — the IF + refold
step is what matters. If you see clashes there, the refolding step
failed to converge; check `refolding_rmsd` — high values mean the
designed backbone is unrealistic. Either rerun with `--num_designs`
higher and keep the best by quality rank, or relax the binding-site
constraint and let the model find a more realistic geometry.
