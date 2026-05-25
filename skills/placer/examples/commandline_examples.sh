#!/bin/bash
# =============================================================================
# PLACER command-line examples, run through the Apptainer/Singularity SIF.
#
# Build the image first (see examples/PLACER.def):
#     apptainer build --fakeroot placer.sif PLACER.def
#
# These examples use the inputs that ship INSIDE the image
# (/opt/PLACER/examples/inputs, /opt/PLACER/examples/ligands) so they run
# out of the box. Output goes to ./out on the host (apptainer auto-mounts $PWD).
#
# Reusable settings:
SIF=./placer.sif
RUN="apptainer exec --nv $SIF python /opt/PLACER/run_PLACER.py"
W=/opt/PLACER/weights/PLACER_model_1.pt   # absolute in-container weights path
IN=/opt/PLACER/examples/inputs
LIG=/opt/PLACER/examples/ligands
mkdir -p out
# =============================================================================

# 1) Dock an inhibitor in a P450 pocket, keeping heme fixed.
#    (heme is auto-fixed because it's not in --predict_ligand)
$RUN --ifile $IN/4dtz.cif --odir out --rerank prmsd --suffix D-LDP-501 \
     -n 50 --predict_ligand D-LDP-501 --weights $W

# 2) Dock inhibitor AND heme simultaneously, scoring both ligands.
$RUN --ifile $IN/4dtz.cif --odir out --rerank prmsd --suffix LDP-HEM \
     -n 50 --predict_ligand D-LDP-501 C-HEM-500 --predict_multi --weights $W

# 3) Predict heme in a de novo protein, refining ligand atom typing from MOL2.
$RUN --ifile $IN/dnHEM1.pdb --odir out --rerank prmsd \
     -n 50 --ligand_file HEM:$LIG/HEM.mol2 --weights $W

# 4) Sidechain prediction with heme fixed; crop centered on a residue.
$RUN --ifile $IN/dnHEM1.pdb --odir out --suffix A149_fixHEM \
     -n 50 --ligand_file HEM:$LIG/HEM.mol2 --fixed_ligand HEM \
     --target_res A-149 --weights $W

# 5) APO sidechain prediction — no ligand, so a crop center is REQUIRED.
$RUN --ifile $IN/dnHEM1_apo.pdb --odir out --suffix A149 \
     -n 50 --target_res A-149 --weights $W

# 6) Mutate a position to a non-canonical residue loaded from a residue JSON;
#    omit the existing small molecule from the prediction (--no-use_sm).
$RUN --ifile $IN/denovo_SER_hydrolase.pdb --odir out --suffix 75I \
     -n 50 --mutate 128A:75I --residue_json $LIG/75I.json --no-use_sm \
     --weights $W

# =============================================================================
# Using YOUR OWN inputs from the host:
#   - apptainer auto-mounts $PWD and $HOME, so relative paths under them work:
#
#       $RUN --ifile my_complex.pdb --odir out -n 100 --rerank prmsd \
#            --predict_ligand A-LIG-1 --weights $W
#
#   - for paths outside $PWD/$HOME, bind-mount them:
#
#       apptainer exec --nv --bind /data:/data $SIF \
#           python /opt/PLACER/run_PLACER.py \
#           --ifile /data/complex.cif --odir /data/out -n 100 \
#           --rerank prmsd --weights $W
# =============================================================================
