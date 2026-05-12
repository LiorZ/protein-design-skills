"""
minimal_pipeline.py
===================

The simplest non-trivial ProtFlow pipeline: load PDBs, compute DSSP and
ProtParam metrics, filter on instability, save.

No GPU, no design — just demonstrates the Poses / Runner / JobStarter
plumbing on metrics that are pure-Python or shell out to small binaries.

Usage
-----
    python minimal_pipeline.py --pdb_dir ./my_pdbs/ --out_dir ./run_minimal/ --local
"""
import argparse

from protflow.poses import Poses
from protflow.jobstarters import LocalJobStarter, SbatchArrayJobstarter
from protflow.metrics.dssp import DSSP
from protflow.metrics.protparam import ProtParam


def main(args):
    js = (
        LocalJobStarter(max_cores=args.cores)
        if args.local
        else SbatchArrayJobstarter(max_cores=args.cores, options="--time=00:30:00")
    )

    poses = Poses(
        poses=args.pdb_dir,
        glob_suffix="*.pdb",
        work_dir=args.out_dir,
        storage_format="json",
        jobstarter=js,
    )
    print(f"Loaded {len(poses)} poses.")

    # 1) Secondary structure summary
    poses = DSSP().run(poses, prefix="dssp", overwrite=args.overwrite)

    # 2) Sequence properties (pI, instability, GRAVY, etc.)
    poses = ProtParam().run(poses, prefix="prot", pH=7.4, overwrite=args.overwrite)

    # 3) Filter: instability < 40 (Guruprasad's "stable" threshold)
    poses.filter_poses_by_value(
        score_col="prot_instability_index",
        value=40.0,
        operator="<",
        prefix="stable_only",
        plot=True,
        fail_on_empty=False,
    )

    # 4) Filter: at least 30% helix
    poses.filter_poses_by_value(
        score_col="dssp_percent_helix",
        value=0.30,
        operator=">=",
        prefix="helix_rich",
        plot=True,
        fail_on_empty=False,
    )

    # 5) Persist
    poses.save_scores()
    print(f"Done. {len(poses)} surviving poses saved to {poses.scorefile}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--pdb_dir", required=True, help="Directory of input PDBs")
    p.add_argument("--out_dir", required=True, help="Working directory")
    p.add_argument("--cores", type=int, default=10)
    p.add_argument("--local", action="store_true", help="Use LocalJobStarter instead of SLURM")
    p.add_argument("--overwrite", action="store_true")
    main(p.parse_args())
