"""Fold a single sequence with ESMFold and write a PDB.

Requires:
    pip install "fair-esm[esmfold]"
    pip install 'dllogger @ git+https://github.com/NVIDIA/dllogger.git'
    pip install 'openfold @ git+https://github.com/aqlaboratory/openfold.git@4b41059694619831a7db195b7e0988fc4ff3a307'

Multimers: pass `--seq "chain1:chain2"` with chains separated by colons.
"""

import argparse
from pathlib import Path

import torch
import esm

DEFAULT_SEQ = "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", default=DEFAULT_SEQ,
                    help="Sequence to fold. Use ':' to separate multimer chains.")
    ap.add_argument("-o", "--out", default="result.pdb")
    ap.add_argument("--chunk-size", type=int, default=None,
                    help="Axial-attention chunk size; lower = less memory")
    args = ap.parse_args()

    model = esm.pretrained.esmfold_v1().eval()
    if torch.cuda.is_available():
        model = model.cuda()
    if args.chunk_size is not None:
        model.set_chunk_size(args.chunk_size)

    with torch.no_grad():
        out = model.infer([args.seq])
        pdb = model.output_to_pdb(out)[0]

    Path(args.out).write_text(pdb)
    print(f"wrote {args.out}")
    print(f"mean pLDDT = {float(out['mean_plddt'][0]):.2f}")
    print(f"pTM        = {float(out['ptm'][0]):.3f}")


if __name__ == "__main__":
    main()
