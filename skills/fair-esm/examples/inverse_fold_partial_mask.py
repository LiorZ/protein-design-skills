"""Partially mask a span of backbone coordinates with `np.inf`, then
sample sequences for the masked region only, leaving the rest of the
sequence equal to the wild type.

This is the canonical "design only residues i..j" pattern with ESM-IF1.

Run:
    python inverse_fold_partial_mask.py target.pdb --chain C --span 10 30 --num-samples 5
"""

import argparse
from copy import deepcopy
from pathlib import Path

import numpy as np
import torch

import esm
import esm.inverse_folding


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdb")
    ap.add_argument("--chain", default="A")
    ap.add_argument("--span", type=int, nargs=2, required=True,
                    metavar=("START", "END"),
                    help="0-based half-open [START, END) range of residues to redesign")
    ap.add_argument("--num-samples", type=int, default=5)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--out", default="partial_designs.fasta")
    args = ap.parse_args()

    s, e = args.span
    model, alphabet = esm.pretrained.esm_if1_gvp4_t16_142M_UR50()
    model = model.eval()
    if torch.cuda.is_available():
        model = model.cuda()

    coords, native_seq = esm.inverse_folding.util.load_coords(args.pdb, args.chain)
    print(f"native (len {len(native_seq)}): masking residues [{s}, {e})")

    # 1) Set masked coordinates to inf so the encoder ignores them.
    masked_coords = deepcopy(coords)
    masked_coords[s:e] = np.inf

    # 2) Constrain the decoder: keep WT outside the span, design inside.
    #    `partial_seq` is a list of letters / special tokens.
    partial_seq = list(native_seq)
    for i in range(s, e):
        partial_seq[i] = "<mask>"

    # Quick native-LL baseline on the masked backbone:
    ll_native, _ = esm.inverse_folding.util.score_sequence(
        model, alphabet, masked_coords, native_seq
    )
    print(f"native LL on masked backbone: {ll_native:.3f}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        for i in range(args.num_samples):
            sampled = model.sample(
                masked_coords,
                partial_seq=partial_seq,
                temperature=args.temperature,
            )
            new_span = sampled[s:e]
            print(f"  sample {i+1}: span = {new_span}")
            f.write(f">sample_{i+1} span={s}-{e}\n{sampled}\n")


if __name__ == "__main__":
    main()
