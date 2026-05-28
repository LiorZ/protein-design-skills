#!/usr/bin/env bash
# Copy-paste invocations for the esm-biohub SIF.
# Assumes:  export SINGULARITY_HOME=/path/to/dir/with/esm.sif
set -euo pipefail

SIF="${SINGULARITY_HOME:?must export SINGULARITY_HOME}/esm.sif"

# -----------------------------------------------------------------------------
# 1) Build the SIF (one-time)
# -----------------------------------------------------------------------------
# Run from inside ~/Repos/esm_biohub so the %files paths resolve.
#   cd ~/Repos/esm_biohub
#   apptainer build --fakeroot "$SIF" esm.def
#
# Or without fakeroot:
#   sudo apptainer build "$SIF" esm.def

# -----------------------------------------------------------------------------
# 2) Smoke test (CPU import; no GPU needed)
# -----------------------------------------------------------------------------
apptainer exec "$SIF" python -c "import esm, torch; print('esm', esm.__version__, '/ torch', torch.__version__)"

# -----------------------------------------------------------------------------
# 3) Verify GPU access (--nv exposes host NVIDIA driver/libs)
# -----------------------------------------------------------------------------
apptainer exec --nv "$SIF" python -c "import torch; print('cuda available:', torch.cuda.is_available(), '/ devices:', torch.cuda.device_count())"

# -----------------------------------------------------------------------------
# 4) HF cache: default (zero-config — host ~/.cache/huggingface is auto-mounted)
# -----------------------------------------------------------------------------
huggingface-cli login                                              # once, gated weights (ESMC-6B)
apptainer exec --nv "$SIF" \
    python -c "from huggingface_hub import HfApi; print(HfApi().whoami())"

# -----------------------------------------------------------------------------
# 5) HF cache: bind to scratch (when $HOME is small/slow)
# -----------------------------------------------------------------------------
HFCACHE="/scratch/$USER/huggingface"
mkdir -p "$HFCACHE"
apptainer exec --nv \
    --bind "$HFCACHE":"$HOME/.cache/huggingface" \
    "$SIF" python my_script.py

# Or rewrite $HF_HOME inside the container:
apptainer exec --nv \
    --bind "$HFCACHE":/hf_cache --env HF_HOME=/hf_cache \
    "$SIF" python my_script.py

# -----------------------------------------------------------------------------
# 6) Pre-warm the HF cache (download every model once, then run offline)
# -----------------------------------------------------------------------------
apptainer exec --nv "$SIF" python - <<'PY'
from huggingface_hub import snapshot_download
for repo in ["Biohub/ESMC-300M", "Biohub/ESMC-600M",
             # "Biohub/ESMC-6B",  # gated — accept terms + huggingface-cli login first
             "Biohub/ESMFold2"]:
    print("Fetching", repo)
    snapshot_download(repo)
PY

# -----------------------------------------------------------------------------
# 7) Run a Python script (the %runscript is `exec python "$@"`)
# -----------------------------------------------------------------------------
apptainer run --nv "$SIF" my_script.py --some-arg

# -----------------------------------------------------------------------------
# 8) One-liners
# -----------------------------------------------------------------------------
# Embed a sequence with ESMC-300M (ungated):
apptainer exec --nv "$SIF" python - <<'PY'
from esm.models.esmc import ESMC
from esm.sdk.api import ESMProtein, LogitsConfig
m = ESMC.from_pretrained("esmc_300m").to("cuda")
prot = ESMProtein(sequence="MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICTTGK")
out = m.logits(m.encode(prot), LogitsConfig(sequence=True, return_embeddings=True))
print("logits:", out.logits.sequence.shape, " embeds:", out.embeddings.shape)
PY

# Fold a monomer with ESMFold2:
apptainer exec --nv "$SIF" python - <<'PY'
from transformers.models.esmfold2.modeling_esmfold2 import ESMFold2Model
from esm.models.esmfold2 import (ProteinInput, StructurePredictionInput, ESMFold2InputBuilder)
m = ESMFold2Model.from_pretrained("biohub/ESMFold2").cuda().eval()
spi = StructurePredictionInput(sequences=[ProteinInput(id="A",
    sequence="MIEIKDKQLTGLRFIDLFAGLGGFRLALESCGAECVYSNEWDKYAQEVYEMNFGEKPEGDITQ")])
res = ESMFold2InputBuilder().fold(m, spi, num_loops=3, num_sampling_steps=50, seed=0)
print(f"pLDDT={float(res.plddt.mean()):.3f} pTM={res.ptm:.3f} ipTM={res.iptm:.3f}")
open("monomer.cif","w").write(res.complex.to_mmcif())
PY

# -----------------------------------------------------------------------------
# 9) Interactive shell with the env on PATH
# -----------------------------------------------------------------------------
apptainer shell --nv "$SIF"
# Inside:
#   Apptainer> which python                   # /opt/venv/bin/python
#   Apptainer> python -c "import esm; print(esm.__version__)"

# -----------------------------------------------------------------------------
# 10) Jupyter on the cookbook
# -----------------------------------------------------------------------------
apptainer exec --nv "$SIF" \
    jupyter notebook --no-browser --ip 0.0.0.0 --port 8888 /opt/esm/cookbook

# -----------------------------------------------------------------------------
# 11) Pick a specific GPU
# -----------------------------------------------------------------------------
apptainer exec --nv --env CUDA_VISIBLE_DEVICES=0 "$SIF" python my_script.py

# -----------------------------------------------------------------------------
# 12) Cluster pattern: shared HF cache + private scratch for downloads
# -----------------------------------------------------------------------------
apptainer exec --nv \
    --bind /shared/hf_cache:/shared/hf_cache:ro \
    --bind "/scratch/$USER/hf:/scratch_hf" \
    --env HF_HOME=/scratch_hf --env HF_HUB_CACHE=/scratch_hf \
    "$SIF" python my_script.py
