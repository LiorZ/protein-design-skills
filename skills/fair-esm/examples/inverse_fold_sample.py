"""Sample N sequence designs for a single chain of a PDB / mmCIF target.

Run:
    python inverse_fold_sample.py target.pdb --chain C --num-samples 8

The output is a FASTA with one sequence per sample. Native sequence
recovery is printed to stderr.
"""

import argparse
import re
from pathlib import Path

import numpy as np
import torch

import esm
import esm.inverse_folding


def has_long_repeat(seq: str, n: int = 5) -> bool:
    """ESM-IF1 sometimes emits homopolymer runs (e.g. EEEEEEEE).
    The README explicitly says to filter these. Returns True if any
    letter is repeated `n` or more times in a row."""
    return bool(re.search(r"(.)\1{%d,}" % (n - 1), seq))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdb")
    ap.add_argument("--chain", default="A")
    ap.add_argument("--num-samples", type=int, default=8)
    ap.add_argument("--temperature", type=float, default=1.0,
                    help="1e-6 ≈ greedy, 1.0 = default diversity")
    ap.add_argument("--out", default="sampled.fasta")
    ap.add_argument("--allow-repeats", action="store_true",
                    help="Do not filter sampled sequences with long AA repeats")
    args = ap.parse_args()

    model, _ = esm.pretrained.esm_if1_gvp4_t16_142M_UR50()
    model = model.eval()
    if torch.cuda.is_available():
        model = model.cuda()

    coords, native_seq = esm.inverse_folding.util.load_coords(args.pdb, args.chain)
    print(f"native (len {len(native_seq)}): {native_seq[:60]}...")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    kept = 0
    with out_path.open("w") as f:
        for i in range(args.num_samples):
            sampled = model.sample(coords, temperature=args.temperature)
            if not args.allow_repeats and has_long_repeat(sampled):
                print(f"  sample {i+1}: skipped (homopolymer run)")
                continue
            recovery = float(np.mean([a == b for a, b in zip(native_seq, sampled)]))
            print(f"  sample {i+1}: recovery={recovery:.2f}  {sampled[:60]}...")
            f.write(f">sample_{i+1} recovery={recovery:.3f} T={args.temperature}\n{sampled}\n")
            kept += 1

    print(f"wrote {kept} / {args.num_samples} sequences to {out_path}")


if __name__ == "__main__":
    main()
