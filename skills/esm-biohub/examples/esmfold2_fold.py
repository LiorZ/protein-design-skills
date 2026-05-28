"""Fold a protein + DNA + ligand complex with ESMFold2 locally.

Run inside the SIF:
    apptainer exec --nv "$SINGULARITY_HOME"/esm.sif python esmfold2_fold.py
"""

from __future__ import annotations

import torch

from esm.models.esmfold2 import (
    DNAInput,
    ESMFold2InputBuilder,
    LigandInput,
    Modification,
    ProteinInput,
    StructurePredictionInput,
)
from transformers.models.esmfold2.modeling_esmfold2 import ESMFold2Model


HHAI = (
    "MIEIKDKQLTGLRFIDLFAGLGGFRLALESCGAECVYSNEWDKYAQEVYEMNFGEKPEGDITQVNEKTIPDH"
    "DILCAGFPCQAFSISGKQKGFEDSRGTLFFDIARIVREKKPKVVFMENVKNFASHDNGNTLEVVKNTMNELD"
    "YSFHAKVLNALDYGIPQKRERIYMICFRNDLNIQNFQFPKPFELNTFVKDLLLPDSEVEHLVIDRKDLVMTN"
    "QEIEQTTPKTVRLGIVGKGGQGERIYSTRGIAITLSAYGGGIFAKTGGYLVNGKTRKLHPRECARVMGYPDS"
    "YKVHPSTSQAYKQFGNSVVINVLQYIAYNIGSSLNFKPY"
)


def main(out_cif: str = "1mht_pred.cif"):
    if not torch.cuda.is_available():
        raise RuntimeError("ESMFold2 needs a GPU. Pass --nv when running apptainer.")

    print("Loading biohub/ESMFold2 ...")
    model = ESMFold2Model.from_pretrained("biohub/ESMFold2").cuda().eval()

    spi = StructurePredictionInput(
        sequences=[
            ProteinInput(id="A", sequence=HHAI),
            DNAInput(
                id="B",
                sequence="GATAGCGCTATC",
                modifications=[Modification(position=5, ccd="C36")],
            ),
            DNAInput(
                id="C",
                sequence="TGATAGCGCTATC",
                modifications=[Modification(position=6, ccd="C36")],
            ),
            LigandInput(id="L", ccd=["SAH"]),
        ]
    )

    builder = ESMFold2InputBuilder()
    result = builder.fold(
        model,
        spi,
        num_loops=3,
        num_sampling_steps=50,
        num_diffusion_samples=1,
        seed=0,
    )

    print(
        f"pLDDT mean: {float(result.plddt.mean()):.3f}  "
        f"pTM: {result.ptm:.3f}  ipTM: {result.iptm:.3f}"
    )
    with open(out_cif, "w") as f:
        f.write(result.complex.to_mmcif())
    print(f"Wrote {out_cif}")


if __name__ == "__main__":
    main()
