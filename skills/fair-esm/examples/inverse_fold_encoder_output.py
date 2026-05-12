"""Extract the L × 512 ESM-IF1 encoder output as a structure
representation. Useful as a learned descriptor of backbone geometry for
clustering / regression / downstream ML.

Run:
    python inverse_fold_encoder_output.py target.pdb --chain C --out rep.npy
"""

import argparse
from pathlib import Path

import numpy as np
import torch

import esm
import esm.inverse_folding


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdb")
    ap.add_argument("--chain", default="A")
    ap.add_argument("--multichain-context", nargs="+", default=None,
                    help="If set, run multi-chain encoder using these chain ids; "
                         "the target chain (--chain) is sliced out of the output.")
    ap.add_argument("--out", default="encoder_rep.npy")
    args = ap.parse_args()

    model, alphabet = esm.pretrained.esm_if1_gvp4_t16_142M_UR50()
    model = model.eval()
    if torch.cuda.is_available():
        model = model.cuda()

    if args.multichain_context:
        import esm.inverse_folding.multichain_util as inv_m
        structure = esm.inverse_folding.util.load_structure(args.pdb, args.multichain_context)
        coords, _ = inv_m.extract_coords_from_complex(structure)
        rep = inv_m.get_encoder_output_for_complex(model, alphabet, coords, args.chain)
    else:
        coords, native_seq = esm.inverse_folding.util.load_coords(args.pdb, args.chain)
        rep = esm.inverse_folding.util.get_encoder_output(model, alphabet, coords)

    rep_np = rep.detach().cpu().numpy()
    print(f"encoder rep shape: {rep_np.shape}    (L × 512)")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    np.save(args.out, rep_np)
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
