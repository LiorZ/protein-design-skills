"""Design sequences for one chain conditioned on the full multi-chain
backbone of a complex.

Run:
    python inverse_fold_multichain.py complex.pdb --target C --context A B C D
"""

import argparse
from pathlib import Path

import torch

import esm
import esm.inverse_folding
import esm.inverse_folding.multichain_util as inv_m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdb")
    ap.add_argument("--target", required=True,
                    help="Chain to redesign sequences for")
    ap.add_argument("--context", nargs="+", default=None,
                    help="All chain ids to load (defaults to every chain in file). "
                         "Target chain must be in this list.")
    ap.add_argument("--num-samples", type=int, default=4)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--out", default="multichain_designs.fasta")
    args = ap.parse_args()

    model, alphabet = esm.pretrained.esm_if1_gvp4_t16_142M_UR50()
    model = model.eval()
    if torch.cuda.is_available():
        model = model.cuda()

    structure = esm.inverse_folding.util.load_structure(args.pdb, args.context)
    coords, native_seqs = inv_m.extract_coords_from_complex(structure)
    print(f"loaded chains: {list(coords.keys())}")
    print(f"target chain {args.target} native (len {len(native_seqs[args.target])})")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for i in range(args.num_samples):
            seq = inv_m.sample_sequence_in_complex(
                model, coords, args.target, temperature=args.temperature
            )
            ll_full, ll_wc = inv_m.score_sequence_in_complex(
                model, alphabet, coords, args.target, seq
            )
            print(f"  sample {i+1}: ll_full={ll_full:.3f} ll_with_coord={ll_wc:.3f}")
            f.write(f">sample_{i+1} target={args.target} ll_full={ll_full:.3f}\n{seq}\n")

    print(f"wrote {args.num_samples} sequences to {out_path}")


if __name__ == "__main__":
    main()
