#!/usr/bin/env bash
# Protenix via Apptainer — copy-paste examples.
#
# These assume the ready-made setup in the Protenix repo:
#   ~/Repos/Protenix/apptainer/{protenix.def,build.sh,download_weights.sh,run_protenix.sh}
# Run them from the repo root so the bundled examples/*.json resolve, OR set
# absolute paths. The run_protenix.sh wrapper adds --nv and bind-mounts weights.
#
# One-time setup:
#   cd ~/Repos/Protenix
#   bash apptainer/build.sh                                            # -> apptainer/protenix.sif
#   PROTENIX_ROOT_DIR=/shared/ModelWeights/Protenix bash apptainer/download_weights.sh
set -euo pipefail

cd ~/Repos/Protenix

RUN="apptainer/run_protenix.sh"          # wrapper: --nv + weights bind-mount
# Point the wrapper at your weights location if not the default:
# export PROTENIX_ROOT_DIR=/shared/ModelWeights/Protenix
# export PROTENIX_SIF=apptainer/protenix.sif

# ---------------------------------------------------------------------------
# 1) Minimal: fold a single protein (auto MSA search), recommended base model.
# ---------------------------------------------------------------------------
$RUN pred \
    -i examples/input.json \
    -o ./output \
    -n protenix_base_default_v1.0.0 \
    --use_default_params true \
    --seeds 101 --sample 5

# ---------------------------------------------------------------------------
# 2) Multi-job file (protein+DNA, protein+ligand+ion, protein+DNA+ligand).
#    example.json holds three jobs; each gets its own output sub-tree.
# ---------------------------------------------------------------------------
$RUN pred -i examples/example.json -o ./output \
    -n protenix_base_default_v1.0.0 --use_default_params true

# ---------------------------------------------------------------------------
# 3) High-throughput screening: fast tiny/mini model, many seeds.
# ---------------------------------------------------------------------------
$RUN pred -i ./jobs_dir/ -o ./screen_out \
    -n protenix_mini_default_v0.5.0 --use_default_params true \
    --seeds 1,2,3,4,5 --sample 1

# ---------------------------------------------------------------------------
# 4) Maximize accuracy with multiple seeds × samples (inference-time scaling).
# ---------------------------------------------------------------------------
$RUN pred -i examples/input.json -o ./output_deep \
    -n protenix_base_default_v1.0.0 --use_default_params true \
    --seeds 101,102,103,104 --sample 25

# ---------------------------------------------------------------------------
# 5) Use templates (v1.0.0 / 20250630 / v2 only). Auto-searches if no path.
# ---------------------------------------------------------------------------
$RUN pred -i examples/examples_with_template/example_9fm7.json -o ./output \
    -n protenix_base_default_v1.0.0 --use_default_params true \
    --use_template true

# ---------------------------------------------------------------------------
# 6) Pocket / contact constraints — needs the constraint checkpoint.
# ---------------------------------------------------------------------------
$RUN pred -i examples/example_constraint_msa.json -o ./output \
    -n protenix_base_constraint_v0.5.0 --use_default_params true

# ---------------------------------------------------------------------------
# 7) Single-sequence (no MSA) — orphan sequence or speed.
# ---------------------------------------------------------------------------
$RUN pred -i examples/input.json -o ./output_nomsa \
    -n protenix_base_default_v1.0.0 --use_default_params true \
    --use_msa false

# ---------------------------------------------------------------------------
# 8) Input prep / conversion utilities.
# ---------------------------------------------------------------------------
# PDB/CIF -> input JSON:
$RUN json -i examples/7pzb.pdb -o ./jsons --assembly_id 1
# MSA search only (cache, then predict from the updated JSON):
$RUN msa -i examples/example_without_msa.json -o ./prep
# MSA + template search:
$RUN mt  -i examples/example_without_msa.json -o ./prep
# Full preprocess (MSA + template + RNA MSA):
$RUN prep -i examples/examples_with_rna_msa/example_9gmw_2.json -o ./prep

# ---------------------------------------------------------------------------
# 9) Split CPU prep from GPU predict (cluster-friendly).
# ---------------------------------------------------------------------------
# CPU/prep node:
$RUN prep -i my_job.json -o ./prep
# GPU node (MSAs already cached in the updated JSON):
$RUN pred -i ./prep/my_job-final-updated.json -o ./out \
    -n protenix_base_default_v1.0.0 --use_default_params true

# ---------------------------------------------------------------------------
# 10) Manual invocation (no wrapper) + restrict to GPU 0.
# ---------------------------------------------------------------------------
WEIGHTS=/shared/ModelWeights/Protenix
apptainer run --nv \
    --bind "$WEIGHTS:$WEIGHTS" \
    --env "PROTENIX_ROOT_DIR=$WEIGHTS" \
    --env "CUDA_VISIBLE_DEVICES=0" \
    apptainer/protenix.sif pred -i examples/input.json -o ./output \
    -n protenix_base_default_v1.0.0 --use_default_params true

# Output for each job: output/<name>/<seed>/<name>_<seed>_sample_*.cif
#                      + ..._summary_confidence_sample_*.json   (rank by ranking_score)
</content>
