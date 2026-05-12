"""Score a FASTA of variant sequences against a fixed backbone using
ESM-IF1 conditional log-likelihoods.

Output is a CSV: seqid, ll_fullseq, ll_with_coord, perplexity

Run:
    python inverse_fold_score.py target.pdb variants.fa --chain C --out scores.csv
"""

import argparse
import csv
from pathlib import Path

import numpy as np
import torch
from biotite.sequence.io.fasta import FastaFile, get_sequences
from tqdm import tqdm

import esm
import esm.inverse_folding


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdb")
    ap.add_argument("fasta")
    ap.add_argument("--chain", default="A")
    ap.add_argument("--out", default="scores.csv")
    ap.add_argument("--multichain-backbone", action="store_true",
                    help="Condition on the full multi-chain complex backbone")
    args = ap.parse_args()

    model, alphabet = esm.pretrained.esm_if1_gvp4_t16_142M_UR50()
    model = model.eval()
    if torch.cuda.is_available():
        model = model.cuda()

    if args.multichain_backbone:
        import esm.inverse_folding.multichain_util as inv_m
        structure = esm.inverse_folding.util.load_structure(args.pdb)   # all chains
        coords, _native = inv_m.extract_coords_from_complex(structure)

        def score(seq):
            return inv_m.score_sequence_in_complex(
                model, alphabet, coords, args.chain, seq
            )
    else:
        coords, _native = esm.inverse_folding.util.load_coords(args.pdb, args.chain)

        def score(seq):
            return esm.inverse_folding.util.score_sequence(model, alphabet, coords, seq)

    ff = FastaFile()
    ff.read(args.fasta)
    seqs = get_sequences(ff)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seqid", "ll_fullseq", "ll_with_coord", "perplexity"])
        for sid, seq in tqdm(seqs.items()):
            ll_full, ll_wc = score(str(seq))
            w.writerow([sid, f"{ll_full:.4f}", f"{ll_wc:.4f}", f"{float(np.exp(-ll_full)):.4f}"])

    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
