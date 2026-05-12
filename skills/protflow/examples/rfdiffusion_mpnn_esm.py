"""
rfdiffusion_mpnn_esm.py
=======================

De novo monomer design with self-consistency validation.

Pipeline
--------
    1. Start from empty Poses (no input PDB).
    2. RFdiffusion: N backbones of L residues.
    3. SolubleMPNN: K sequences per backbone.
    4. ESMFold: predict each sequence's structure.
    5. BackboneRMSD: align predictions to their RFdiffusion backbone.
    6. Filter: RMSD <= 2.0 Å AND mean predicted pLDDT >= 0.7.
    7. Composite-rank and keep top-50 designs.

This is the canonical "self-consistency" workflow used to triage de novo
monomer campaigns.

Usage
-----
    python rfdiffusion_mpnn_esm.py --length 70 --n_bb 50 --n_seq 8 \
        --out_dir ./mono_run/
"""
import argparse

from protflow.poses import Poses
from protflow.jobstarters import LocalJobStarter, SbatchArrayJobstarter
from protflow.tools.rfdiffusion import RFdiffusion
from protflow.tools.ligandmpnn import LigandMPNN
from protflow.tools.esmfold import ESMFold
from protflow.metrics.rmsd import BackboneRMSD


def make_jobstarter(args):
    if args.local:
        return LocalJobStarter(max_cores=args.cores)
    return SbatchArrayJobstarter(
        max_cores=args.cores,
        gpus=1,
        options=f"--time={args.walltime} --partition={args.partition}",
    )


def main(args):
    gpu = make_jobstarter(args)

    poses = Poses(
        poses=None,                        # start empty — RFdiffusion will create backbones
        work_dir=args.out_dir,
        storage_format="pickle",            # pickle keeps ResidueSelection objects native
        jobstarter=gpu,
    )

    # 1) Generate N backbones of length L
    poses = RFdiffusion().run(
        poses,
        prefix="diff",
        num_diffusions=args.n_bb,
        options=f"'contigmap.contigs=[{args.length}-{args.length}]'",
        overwrite=args.overwrite,
    )
    print(f"After RFdiffusion: {len(poses)} backbones.")

    # 2) Design K sequences per backbone. SolubleMPNN is a sensible default for de novo.
    poses = LigandMPNN().run(
        poses,
        prefix="mpnn",
        nseq=args.n_seq,
        model_type="soluble_mpnn",
        options="--temperature 0.1",
        overwrite=args.overwrite,
    )
    print(f"After MPNN: {len(poses)} sequences total (K={args.n_seq} per backbone).")

    # 3) Fold every designed sequence
    poses = ESMFold().run(poses, prefix="esm", overwrite=args.overwrite)

    # 4) RMSD vs the original RFdiffusion backbone
    #    diff_location is the column RFdiffusion wrote pointing at its PDB.
    poses = BackboneRMSD(atoms=["N", "CA", "C", "O"]).run(
        poses,
        prefix="rmsd",
        ref_col="diff_location",
        overwrite=args.overwrite,
    )

    # 5) Self-consistency filters
    poses.filter_poses_by_value(
        score_col="rmsd_rmsd", value=2.0, operator="<=",
        prefix="sc_rmsd", plot=True, fail_on_empty=False,
    )
    poses.filter_poses_by_value(
        score_col="esm_plddt", value=0.7, operator=">=",
        prefix="sc_plddt", plot=True, fail_on_empty=False,
    )

    # 6) Composite score: lower RMSD and higher pLDDT both reduce the score
    poses.calculate_composite_score(
        name="self_consistency",
        scoreterms=["rmsd_rmsd", "esm_plddt", "esm_ptm"],
        weights=[1.0, -1.0, -1.0],
        plot=True,
    )

    # 7) Keep the top 50
    poses.filter_poses_by_rank(
        n=50, score_col="self_consistency", ascending=True,
        prefix="final", plot=True,
    )

    poses.save_scores()
    poses.save_poses(out_path=f"{args.out_dir}/final_pdbs/")
    print(f"Done. {len(poses)} final designs written to {args.out_dir}/final_pdbs/")


if __name__ == "__main__":
    p = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--out_dir", required=True)
    p.add_argument("--length", type=int, default=70, help="Backbone length")
    p.add_argument("--n_bb", type=int, default=50, help="Number of RFdiffusion backbones")
    p.add_argument("--n_seq", type=int, default=8, help="Sequences per backbone")
    p.add_argument("--cores", type=int, default=10)
    p.add_argument("--partition", default="gpu")
    p.add_argument("--walltime", default="08:00:00")
    p.add_argument("--local", action="store_true")
    p.add_argument("--overwrite", action="store_true")
    main(p.parse_args())
