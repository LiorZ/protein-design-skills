"""Embed a few sequences locally with ESMC and print logits + embeddings shapes.

Run inside the SIF:
    apptainer exec --nv "$SINGULARITY_HOME"/esm.sif python esmc_embed.py
"""

from __future__ import annotations

import torch

from esm.models.esmc import ESMC
from esm.sdk.api import ESMProtein, LogitsConfig


SEQS = [
    # GFP wildtype
    ("GFP",
     "MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICTTGKLPVPWPTLVTT"
     "FSYGVQCFSRYPDHMKQHDFFKSAMPEGYVQERTIFFKDDGNYKTRAEVKFEGDTLVNRIELKG"),
    # Human carbonic anhydrase II (PDB 2CBA)
    ("CA2",
     "MSHHWGYGKHNGPEHWHKDFPIAKGERQSPVDIDTHTAKYDPSLKPLSVSYDQATSLRILNNGH"
     "AFNVEFDDSQDKAVLKGGPLDGTYRLIQFHFHWGSLDGQGSEHTVDKKKYAAELHLVHWNTKYGDF"),
]


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"loading ESMC-300M on {device} ...")
    model = ESMC.from_pretrained("esmc_300m", device=torch.device(device))

    for name, seq in SEQS:
        protein = ESMProtein(sequence=seq)
        protein_tensor = model.encode(protein)

        out = model.logits(
            protein_tensor,
            LogitsConfig(
                sequence=True,
                return_embeddings=True,
                return_mean_embedding=True,
            ),
        )

        print(
            f"{name:>5s}  len={len(seq):<3d}  "
            f"logits={tuple(out.logits.sequence.shape)}  "
            f"embeds={tuple(out.embeddings.shape)}  "
            f"mean_embedding={tuple(out.mean_embedding.shape)}"
        )


if __name__ == "__main__":
    main()
