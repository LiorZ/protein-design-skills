"""Extract top SAE features for a sequence using the Biohub Platform.

Run inside the SIF:
    export ESM_API_KEY=biohub-...
    apptainer exec --nv --env ESM_API_KEY \
        "$SINGULARITY_HOME"/esm.sif python sae_features.py
"""

from __future__ import annotations

import os

import torch

from esm.sdk import esmc_client
from esm.sdk.api import (
    ESMProtein,
    ESMProteinError,
    LogitsConfig,
    SAEConfig,
)


SEQ = (
    "MGSNKSKPKDASQRRRSLEPAENVHGAGGGAFPASQTPSKPASADGHRGPSAAFAPAAAEPKL"
    "FGGFNSSDTVTSPQRAGPLAGGVTTFVALYDYESRTETDLSFKKGERLQIVNNTEGDWWLAHS"
    "LSTGQTGYIPSNYVAPSDSIQAEEWYFGKITRRESERLLLNAENPRGTFLVRESETTKGAYCL"
)


def _max_pool_coo(t: torch.Tensor) -> torch.Tensor:
    """Max-pool a 2D sparse COO tensor along the token axis (axis=0).

    Equivalent to cookbook/snippets/sparse_utils.max_pool — implemented
    here so this example is self-contained.
    """
    t = t.coalesce()
    idx = t.indices()                  # (2, nnz)  rows = token, cols = feature
    val = t.values()                   # (nnz,)
    n_feat = t.size(1)
    pooled = torch.zeros(n_feat, dtype=val.dtype, device=val.device)
    # scatter-max
    pooled.scatter_reduce_(0, idx[1], val, reduce="amax", include_self=True)
    return pooled


def main():
    api_key = os.environ.get("ESM_API_KEY")
    if not api_key:
        raise SystemExit("Set ESM_API_KEY (https://biohub.ai/developer-console/api-keys)")

    client = esmc_client(model="esmc-6b-2024-12", token=api_key)

    sae_cfg = SAEConfig(
        models=["Biohub/ESMC-6B-sae-layer60-k64-codebook16384"],
        normalize_features=True,
    )

    protein_tensor = client.encode(ESMProtein(sequence=SEQ))
    if isinstance(protein_tensor, ESMProteinError):
        raise RuntimeError(protein_tensor.error_msg)

    out = client.logits(
        protein_tensor,
        LogitsConfig(sae_config=sae_cfg),
        return_bytes=False,
    )
    if isinstance(out, ESMProteinError):
        raise RuntimeError(out.error_msg)
    if out.sae_outputs is None:
        raise RuntimeError(f"missing sae_outputs: {out}")

    sae_tensor = out.sae_outputs[sae_cfg.models[0]]   # sparse COO (L+2, 16384)
    # Drop BOS / EOS by slicing rows 1 … L (sparse-safe slicing)
    sae_tensor = sae_tensor.to_dense()[1:-1]
    pooled = sae_tensor.max(dim=0).values             # (16384,)

    top = torch.topk(pooled, k=10)
    print("Top-10 SAE features by max activation across tokens:")
    for v, idx in zip(top.values.tolist(), top.indices.tolist()):
        print(f"  feature {idx:>5d}   max_activation={v:.3f}")


if __name__ == "__main__":
    main()
