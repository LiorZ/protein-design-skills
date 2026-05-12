"""
enzyme_redesign.py
==================

Active-site-preserving redesign of an enzyme: fix the catalytic residues,
let LigandMPNN re-design the pocket-lining residues, relax with Rosetta,
verify identity of the catalytic triad survived.

Pipeline
--------
    1. Load enzyme PDB(s); declare catalytic residues as a motif.
    2. ChainSelector → identify the ligand chain.
    3. DistanceSelector → compute the 5 Å pocket around the ligand.
    4. LigandMPNN with model_type="ligand_mpnn":
       - fixed_res_col = catalytic triad
       - design_res_col = pocket residues
    5. AttnPacker for sidechain repacking.
    6. Rosetta FastRelax for refinement.
    7. SelectionIdentity confirms catalytic triad identity preserved.
    8. ProtParam summary, filter on stable + low GRAVY.

This is the canonical "scaffold the catalytic triad, redesign everything else"
loop used in directed-evolution-style enzyme campaigns.

Usage
-----
    python enzyme_redesign.py \
        --pdb_dir ./enzymes/ \
        --catalytic "A57,A102,A195" \
        --ligand_chain Z \
        --out_dir ./enzyme_run/
"""
import argparse

from protflow.poses import Poses
from protflow.residues import ResidueSelection
from protflow.jobstarters import LocalJobStarter, SbatchArrayJobstarter
from protflow.tools.ligandmpnn import LigandMPNN
from protflow.tools.attnpacker import AttnPacker
from protflow.tools.rosetta import Rosetta
from protflow.tools.residue_selectors import ChainSelector, DistanceSelector
from protflow.metrics.selection_identity import SelectionIdentity
from protflow.metrics.protparam import ProtParam
from protflow.metrics.ligand import LigandContacts, LigandClashes


def make_jobstarter(args, gpu=False):
    if args.local:
        return LocalJobStarter(max_cores=args.cores)
    if gpu:
        return SbatchArrayJobstarter(
            max_cores=args.cores, gpus=1,
            options=f"--time=08:00:00 --partition={args.partition}",
        )
    return SbatchArrayJobstarter(
        max_cores=args.cores * 4,
        options=f"--time=04:00:00 --partition={args.cpu_partition} --mem=8G",
    )


def main(args):
    gpu = make_jobstarter(args, gpu=True)
    cpu = make_jobstarter(args, gpu=False)

    poses = Poses(
        poses=args.pdb_dir,
        glob_suffix="*.pdb",
        work_dir=args.out_dir,
        storage_format="pickle",
        jobstarter=gpu,
    )
    print(f"Loaded {len(poses)} enzymes.")

    # 1) Catalytic triad — tracked as ResidueSelection
    poses.df["catalytic"] = poses.df.apply(
        lambda r: ResidueSelection(args.catalytic), axis=1
    )

    # 2) Identify the ligand chain
    ChainSelector(chain=args.ligand_chain).select(prefix="lig", poses=poses)

    # 3) Pocket = residues within 5 Å of the ligand (excluding the ligand itself)
    DistanceSelector(
        center="lig_residue_selection",
        distance=5.0,
        operator="<=",
        include_center=False,
        noncenter_atoms=None,
    ).select(prefix="pocket", poses=poses)

    # 4) LigandMPNN: fix catalytic triad, design pocket only
    poses = LigandMPNN().run(
        poses,
        prefix="mpnn",
        nseq=args.n_seq,
        model_type="ligand_mpnn",
        fixed_res_col="catalytic",
        design_res_col="pocket_residue_selection",
        options="--temperature 0.1",
        overwrite=args.overwrite,
    )

    # 5) Repack sidechains with AttnPacker
    poses = AttnPacker().run(poses, prefix="pack", overwrite=args.overwrite)

    # 6) Refine with Rosetta FastRelax. CPU jobstarter.
    poses = Rosetta(jobstarter=cpu).run(
        poses,
        prefix="relax",
        rosetta_application="relax.linuxgccrelease",
        nstruct=1,
        options="-relax:fast -relax:constrain_relax_to_start_coords "
                "-ex1 -ex2 -use_input_sc -no_optH false",
        overwrite=args.overwrite,
    )

    # 7) Confirm catalytic triad identity. We expect e.g. 'HDS' (His/Asp/Ser).
    SelectionIdentity(residue_selection="catalytic", onelettercode=True).run(
        poses, prefix="cat_id", overwrite=args.overwrite
    )

    # 8) Ligand contacts / clashes
    poses = LigandContacts(ligand_chain=args.ligand_chain, max_dist=5.0).run(
        poses, prefix="lig_contacts", overwrite=args.overwrite,
    )
    poses = LigandClashes(ligand_chain=args.ligand_chain, factor=0.85).run(
        poses, prefix="lig_clashes", overwrite=args.overwrite,
    )

    # 9) ProtParam summary
    ProtParam().run(poses, prefix="prot", pH=7.4, overwrite=args.overwrite)

    # 10) Filter
    poses.filter_poses_by_value(
        score_col="cat_id_identity", value=args.expected_triad,
        operator="==", prefix="cat_preserved", fail_on_empty=False,
    )
    poses.filter_poses_by_value(
        score_col="lig_clashes_n_clashes", value=0, operator="==",
        prefix="no_clashes", fail_on_empty=False,
    )
    poses.filter_poses_by_value(
        score_col="prot_instability_index", value=40, operator="<",
        prefix="stable", fail_on_empty=False,
    )

    # 11) Composite: maximise ligand contacts, minimise instability
    poses.calculate_composite_score(
        name="enzyme_score",
        scoreterms=["lig_contacts_n_contacts", "prot_instability_index"],
        weights=[-1.0, 0.5],
        plot=True,
    )
    poses.filter_poses_by_rank(
        n=args.top_n, score_col="enzyme_score", ascending=True,
        prefix="final", plot=True,
    )

    poses.save_scores()
    poses.save_poses(out_path=f"{args.out_dir}/final_enzymes/")
    print(f"Done. {len(poses)} final designs at {args.out_dir}/final_enzymes/")


if __name__ == "__main__":
    p = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--pdb_dir", required=True)
    p.add_argument("--out_dir", required=True)
    p.add_argument("--catalytic", required=True,
                   help="Comma-separated catalytic residues (e.g. 'A57,A102,A195')")
    p.add_argument("--ligand_chain", default="Z")
    p.add_argument("--expected_triad", default="HDS",
                   help="One-letter expected identity of the catalytic motif (in selection order)")
    p.add_argument("--n_seq", type=int, default=8)
    p.add_argument("--top_n", type=int, default=20)
    p.add_argument("--cores", type=int, default=10)
    p.add_argument("--partition", default="gpu")
    p.add_argument("--cpu_partition", default="cpu")
    p.add_argument("--local", action="store_true")
    p.add_argument("--overwrite", action="store_true")
    main(p.parse_args())
