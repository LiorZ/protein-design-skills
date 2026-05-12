"""
predict_protein_ligand.py
=========================

High-throughput AlphaFold3 protein-ligand co-folding from a directory of
FASTA files and a single SMILES (ligand co-folded with every target).

Pipeline
--------
    1. Glob *.fa in --input_dir.
    2. Either:
       - Predict all at once (--predictions_per_day = 0), or
       - Predict in daily batches that respect MMseqs2 server politeness
         (--predictions_per_day > 0).
    3. AlphaFold3 with the ligand attached as an additional_entity.
    4. Aggregate scores across batches.

Adapted from ProtFlow's own scripts/predict_protein_ligand.py.

Usage
-----
    python predict_protein_ligand.py \
        --input_dir ./fastas/ \
        --ligand_file ./lig.smi \
        --output_dir ./af3_run/
"""
import os
import time
import logging
import argparse
from glob import glob

import pandas as pd
import protflow
from protflow.tools.alphafold3 import AlphaFold3
from protflow.runners import Runner
from protflow.poses import Poses


def predict_per_day(model: Runner, files: list, predictions_per_day: int,
                     output_dir: str, smiles: str, samples: int, options: str = None):
    """Predict in daily batches; politely throttles the MMseqs2 server."""
    split_fl = protflow.jobstarters.split_list(files, element_length=predictions_per_day)
    logging.info(f"Split {len(files)} input files into {len(split_fl)} batches of size {predictions_per_day}.")

    predictions_dir = os.path.join(output_dir, "predictions")
    scores_list = []
    for i, fl in enumerate(split_fl, start=1):
        start_time = time.time()
        logging.info(f"Starting prediction of batch {i}.")

        batch = Poses(poses=fl, work_dir=os.path.join(output_dir, f"batch_{i}"))

        std = "--flash_attention_implementation xla --cuda_compute_7x 1"
        opts = f"{std} {options}" if options else std

        model.run(
            poses=batch,
            prefix="af3",
            additional_entities={"ligand": {"id": "Z", "smiles": smiles}},
            nstruct=samples,
            options=opts,
            single_sequence_mode=False,
        )

        scores_list.append(batch.df)
        batch.save_scores()
        batch.save_poses(predictions_dir)
        logging.info(f"Batch {i} finished. Structures in {predictions_dir}")

        # respect a 1-batch-per-day cap
        while time.time() - start_time < 24 * 3600:
            time.sleep(60)

    all_scores = pd.concat(scores_list, axis=0, ignore_index=True).reset_index(drop=True)
    all_scores.to_json(os.path.join(output_dir, "prediction_scores.df.json"))


def predict_all_at_once(model: Runner, files: list, output_dir: str, smiles: str,
                         samples: int, options: str = None):
    poses = Poses(poses=files, work_dir=output_dir)

    std = "--flash_attention_implementation xla --cuda_compute_7x 1"
    opts = f"{std} {options}" if options else std

    model.run(
        poses=poses,
        prefix="af3",
        additional_entities={"ligand": {"id": "Z", "smiles": smiles}},
        nstruct=samples,
        options=opts,
        single_sequence_mode=False,
    )
    poses.save_scores()
    poses.save_poses(os.path.join(output_dir, "predictions"))


def main(args):
    os.makedirs(args.output_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(os.path.join(args.output_dir, "log.txt")),
            logging.StreamHandler(),
        ],
    )

    if args.jobstarter == "sbatch":
        js = protflow.jobstarters.SbatchArrayJobstarter(
            max_cores=args.num_workers, gpus=1,
            options=f"--time={args.walltime} --partition={args.partition}",
        )
    elif args.jobstarter == "local":
        js = protflow.jobstarters.LocalJobStarter(max_cores=args.num_workers)
    else:
        raise ValueError(f"--jobstarter must be sbatch|local; got {args.jobstarter}")

    af3 = AlphaFold3(jobstarter=js)

    with open(args.ligand_file, "r", encoding="utf-8") as f:
        smiles = f.read().strip()

    files = sorted(glob(os.path.join(args.input_dir, "*.fa")))
    if not files:
        raise FileNotFoundError(f"No *.fa found in {args.input_dir}")

    if args.predictions_per_day > 0:
        predict_per_day(af3, files, args.predictions_per_day, args.output_dir,
                         smiles, args.samples, args.prediction_options)
    else:
        predict_all_at_once(af3, files, args.output_dir,
                             smiles, args.samples, args.prediction_options)
    logging.info("Done.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--input_dir", required=True)
    p.add_argument("--ligand_file", required=True, help="File containing one SMILES string")
    p.add_argument("--output_dir", required=True)
    p.add_argument("--jobstarter", default="sbatch", choices=["sbatch", "local"])
    p.add_argument("--samples", type=int, default=5)
    p.add_argument("--prediction_options", default=None)
    p.add_argument("--predictions_per_day", type=int, default=0,
                   help="0 = all at once; >0 = throttle to this many per day")
    p.add_argument("--num_workers", type=int, default=10)
    p.add_argument("--partition", default="gpu")
    p.add_argument("--walltime", default="08:00:00")
    main(p.parse_args())
