"""Minimal ESM-2 forward pass.

Loads a small ESM-2 checkpoint, tokenizes a couple of sequences, runs a
forward pass on CPU, and prints the shapes of the mean and per-token
representations and the attention-based contacts.

Switch the model factory to `esm2_t33_650M_UR50D` (650M, 1280-d) for the
standard "good default" you'd use in real downstream work.

Run:
    python extract_embeddings.py
"""

import torch
import esm

MODEL_FACTORY = esm.pretrained.esm2_t6_8M_UR50D     # 8M, embed_dim 320, layers 0..6
SEQUENCES = [
    ("p1", "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSL"),
    ("p2", "KALTARQQEVFDLIRDHISQTGMPPTRAEIAQRLGFRSPNAAEEH"),
]


def main():
    model, alphabet = MODEL_FACTORY()
    model.eval()                                    # disable dropout
    batch_converter = alphabet.get_batch_converter()

    _, _, tokens = batch_converter(SEQUENCES)       # (B, max_L + 2)
    seq_lens = (tokens != alphabet.padding_idx).sum(1)
    last_layer = model.num_layers                   # 6 for esm2_t6_8M_UR50D

    with torch.no_grad():
        out = model(tokens, repr_layers=[last_layer], return_contacts=True)

    print("logits:           ", tuple(out["logits"].shape))
    print(f"representations[{last_layer}]:", tuple(out["representations"][last_layer].shape))
    print("contacts:         ", tuple(out["contacts"].shape))

    reps = out["representations"][last_layer]
    for i, (label, seq) in enumerate(SEQUENCES):
        L = int(seq_lens[i])                        # includes BOS + EOS
        per_residue = reps[i, 1 : L - 1]            # strip BOS and EOS
        seq_repr = per_residue.mean(0)
        print(f"{label}: per-tok {tuple(per_residue.shape)}, mean {tuple(seq_repr.shape)}")


if __name__ == "__main__":
    main()
