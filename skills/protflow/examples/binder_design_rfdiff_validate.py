"""
binder_design_rfdiff_validate.py
=================================

End-to-end binder design with built-in validation.

Pipeline
--------
    1. Load target PDB; build the hotspot ResidueSelection.
    2. RFdiffusion (PPI mode): N binder backbones around hotspots.
       Carries the hotspot motif via update_motifs.
    3. LigandMPNN (soluble_mpnn): K sequences per backbone, target chain fixed.
    4. AlphaFold3 (or ColabFold/AF2 if you prefer): predict the complex.
    5. Compute interface metrics (LigandContacts to target as proxy,
       MotifRMSD on the hotspot, ipTM filter).
    6. Composite-rank by ipTM + interface RMSD; keep top-N.

This is a typical "design 100s of binders, pick the best to order" workflow.

Usage
-----
    python binder_design_rfdiff_validate.py \
        --target ./my_target.pdb \
        --hotspots "A42,A45,A82" \
        --binder_length 80 \
        --n_bb 200 --n_seq 8 \
        --out_dir ./binder_run/
"""
import argparse

from protflow.poses import Poses
from protflow.residues import ResidueSelection
from protflow.jobstarters import LocalJobStarter, SbatchArrayJobstarter
from protflow.tools.rfdiffusion import RFdiffusion
from protflow.tools.ligandmpnn import LigandMPNN
from protflow.tools.alphafold3 import AlphaFold3
from protflow.tools.residue_selectors import ChainSelector
from protflow.metrics.rmsd import MotifRMSD


def make_jobstarter(args):
    if args.local:
        return LocalJobStarter(max_cores=args.cores)
    return SbatchArrayJobstarter(
        max_cores=args.cores, gpus=1,
        options=f"--time={args.walltime} --partition={args.partition}",
    )


def main(args):
    gpu = make_jobstarter(args)

    # Load the target PDB
    poses = Poses(
        poses=[args.target],
        work_dir=args.out_dir,
        storage_format="pickle",
        jobstarter=gpu,
    )

    # Tag the hotspots as a residue selection that we'll track through diffusion
    poses.df["hotspots"] = poses.df.apply(
        lambda r: ResidueSelection(args.hotspots), axis=1
    )

    # Tag the target chain (assumed A)
    ChainSelector(chain=args.target_chain).select(prefix="target", poses=poses)

    # 1) RFdiffusion: hotspot-guided binder generation
    contig = f"'contigmap.contigs=[{args.target_contig}/0 {args.binder_length}-{args.binder_length}]'"
    ppi    = f"'ppi.hotspot_res=[{args.hotspots}]'"
    poses = RFdiffusion().run(
        poses,
        prefix="diff",
        num_diffusions=args.n_bb,
        multiplex_poses=1,
        options=f"{contig} {ppi} 'denoiser.noise_scale_ca=0' 'denoiser.noise_scale_frame=0'",
        update_motifs=["hotspots", "target_residue_selection"],
        overwrite=args.overwrite,
        fail_on_missing_output_poses=False,
    )
    print(f"After RFdiffusion: {len(poses)} binder backbones.")

    # 2) LigandMPNN: design the *binder* chain (B), fix the *target* chain
    poses = LigandMPNN().run(
        poses,
        prefix="mpnn",
        nseq=args.n_seq,
        model_type="soluble_mpnn",
        fixed_res_col="target_residue_selection",
        options="--temperature 0.1",
        overwrite=args.overwrite,
    )
    print(f"After MPNN: {len(poses)} sequences total.")

    # 3) AlphaFold3 prediction of the *complex* (binder + target).
    #    AF3 reads chains from the input fasta/json; ProtFlow's AF3 runner
    #    handles construction of the JSON inputs from the poses.
    poses = AlphaFold3().run(
        poses,
        prefix="af3",
        nstruct=5,
        options="--flash_attention_implementation xla --cuda_compute_7x 1",
        single_sequence_mode=False,
        use_templates=False,
        return_top_n_models=1,
        overwrite=args.overwrite,
    )

    # 4) Motif RMSD on the hotspot — does the predicted complex preserve the
    #    interaction geometry RFdiffusion designed for?
    poses = MotifRMSD(
        ref_col="diff_location",
        ref_motif="hotspots",
        target_motif="hotspots",
        atoms=["N", "CA", "C", "O"],
    ).run(poses, prefix="hot_rmsd", overwrite=args.overwrite)

    # 5) Filter on ipTM and hotspot RMSD
    poses.filter_poses_by_value(
        score_col="af3_iptm", value=0.6, operator=">=",
        prefix="iptm_passing", plot=True, fail_on_empty=False,
    )
    poses.filter_poses_by_value(
        score_col="hot_rmsd_rmsd", value=2.0, operator="<=",
        prefix="hotspot_passing", plot=True, fail_on_empty=False,
    )

    # 6) Composite rank
    poses.calculate_composite_score(
        name="binder_score",
        scoreterms=["af3_iptm", "af3_ptm", "hot_rmsd_rmsd"],
        weights=[-1.0, -0.5, 1.0],
        plot=True,
    )

    poses.filter_poses_by_rank(
        n=args.top_n, score_col="binder_score", ascending=True,
        prefix="final", plot=True,
    )

    poses.save_scores()
    poses.save_poses(out_path=f"{args.out_dir}/final_binders/")
    print(f"Done. {len(poses)} final binders at {args.out_dir}/final_binders/")


if __name__ == "__main__":
    p = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--target", required=True, help="Target PDB")
    p.add_argument("--target_chain", default="A", help="Chain ID for the target in the input PDB")
    p.add_argument("--target_contig", default="A1-200",
                   help="Contig string for the target portion (e.g. 'A1-200')")
    p.add_argument("--hotspots", default="A42,A45,A82",
                   help="Comma-separated hotspot residues (in input numbering)")
    p.add_argument("--binder_length", type=int, default=80)
    p.add_argument("--n_bb", type=int, default=200, help="Number of binder backbones")
    p.add_argument("--n_seq", type=int, default=8, help="Sequences per backbone")
    p.add_argument("--top_n", type=int, default=50)
    p.add_argument("--out_dir", required=True)
    p.add_argument("--cores", type=int, default=20)
    p.add_argument("--partition", default="gpu")
    p.add_argument("--walltime", default="12:00:00")
    p.add_argument("--local", action="store_true")
    p.add_argument("--overwrite", action="store_true")
    main(p.parse_args())
