"""Extract attention-based contact predictions from ESM-2 and save them
both as a numpy array and (optionally) a matplotlib heatmap.

Run:
    python contact_prediction.py --seq "MKTV..." --out contacts.npy --plot contacts.png
"""

import argparse
from pathlib import Path

import numpy as np
import torch

import esm

DEFAULT_SEQ = (
    "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", default=DEFAULT_SEQ)
    ap.add_argument("--model", default="esm2_t33_650M_UR50D",
                    help="Use any model that ships with regression weights "
                         "(NOT esm1v / esm_if).")
    ap.add_argument("--out", default="contacts.npy")
    ap.add_argument("--plot", default=None,
                    help="If set, write a matplotlib heatmap to this path")
    args = ap.parse_args()

    factory = getattr(esm.pretrained, args.model)
    model, alphabet = factory()
    model.eval()
    if torch.cuda.is_available():
        model = model.cuda()

    bc = alphabet.get_batch_converter()
    _, _, tokens = bc([("p", args.seq)])
    if torch.cuda.is_available():
        tokens = tokens.cuda()

    with torch.no_grad():
        contacts = model.predict_contacts(tokens).cpu().numpy()[0]  # (L, L)

    print(f"contacts shape: {contacts.shape}")
    print(f"long-range contact-prob top-10: {sorted(contacts[np.triu_indices(len(args.seq), k=6)].tolist(), reverse=True)[:10]}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    np.save(args.out, contacts)
    print(f"saved {args.out}")

    if args.plot:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(6, 6))
        plt.imshow(contacts, origin="lower", cmap="Blues")
        plt.colorbar(label="contact probability")
        plt.title(args.model)
        plt.xlabel("residue")
        plt.ylabel("residue")
        plt.tight_layout()
        plt.savefig(args.plot, dpi=200)
        print(f"saved {args.plot}")


if __name__ == "__main__":
    main()
