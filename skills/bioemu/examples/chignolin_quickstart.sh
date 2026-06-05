#!/usr/bin/env bash
#
# BioEmu quickstart — sample 100 conformations of chignolin (10-residue
# fast-folder) and inspect the ensemble.
#
# Runtime: ~30 seconds on an A100. ~5 minutes on a small GPU. Will OOM
# on no GPU (CPU is technically supported but unusably slow).
#
# Prereq: pip install 'bioemu[cuda]'

set -euo pipefail

OUT="${1:-${HOME}/bioemu-chignolin}"

echo "==> Sampling 100 backbones of chignolin (GYDPETGTWG) into ${OUT}"
python -m bioemu.sample \
    --sequence       GYDPETGTWG \
    --num_samples    100 \
    --output_dir     "${OUT}" \
    --batch_size_100 20 \
    --base_seed      42

echo
echo "==> Files produced:"
ls -lh "${OUT}"

echo
echo "==> Loading and summarizing the ensemble:"
python - <<PY
import mdtraj, os
out = os.path.expanduser("${OUT}")
t = mdtraj.load_xtc(f"{out}/samples.xtc", top=f"{out}/topology.pdb")
print(f"  frames:    {t.n_frames}")
print(f"  atoms:     {t.n_atoms}")
print(f"  residues:  {t.n_residues}")

t.superpose(t, frame=0)
rmsd = mdtraj.rmsd(t, t, frame=0)
print(f"  mean RMSD to frame 0: {rmsd.mean():.3f} nm")
print(f"  max  RMSD to frame 0: {rmsd.max():.3f} nm")
print(f"  --> if max > 0.5 nm you have multiple basins (likely folded + unfolded)")
PY

echo
echo "==> Optional next steps:"
echo "  - Reconstruct side chains:"
echo "      python -m bioemu.sidechain_relax \\"
echo "          --pdb-path ${OUT}/topology.pdb --xtc-path ${OUT}/samples.xtc \\"
echo "          --outpath ${OUT}/relaxed"
echo "  - Enable physical steering for longer sequences:"
echo "      python -m bioemu.sample \\"
echo "          --sequence <aa> --num_samples 100 --output_dir <dir> \\"
echo "          --denoiser_config src/bioemu/config/steering/physical_steering.yaml"
