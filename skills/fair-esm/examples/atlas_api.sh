#!/usr/bin/env bash
# Fold a single sequence by hitting the public ESM Metagenomic Atlas API.
# No install needed — but limited to ~400 residues per call and rate-limited.

set -euo pipefail

SEQ="${1:-KVFGRCELAAAMKRHGLDNYRGYSLGNWVCAAKFESNFNTQATNRNTDGSTDYGILQINSRWWCNDGRTPGSRNLCNIPCSALLSSDITASVNCAKKIVSDGNGMNAWVAWRNRCKGTDVQAWIRGCRL}"
OUT="${2:-atlas.pdb}"

curl -fsS -X POST --data "${SEQ}" \
    https://api.esmatlas.com/foldSequence/v1/pdb/ \
    > "${OUT}"

echo "wrote ${OUT}"

# Optional: extract mean pLDDT from the B-factor column with biotite
python - <<'PY'
import sys, biotite.structure.io as bsio
try:
    s = bsio.load_structure("'"${OUT}"'", extra_fields=["b_factor"])
    print(f"mean pLDDT = {s.b_factor.mean():.2f}")
except Exception as e:
    sys.stderr.write(f"(could not parse pLDDT: {e})\n")
PY
