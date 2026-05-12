# Motif Tracking Through Generative Steps

When RFdiffusion (or RFdiffusion3) inpaints / hallucinates new residues, the
output PDB's residue numbering does not match the input's. To keep a
biologically meaningful site (an active site, a binding interface, a
hotspot) tagged through the design pipeline, ProtFlow stores it as a
`ResidueSelection` and re-indexes after every generative step.

## The minimum recipe

```python
from protflow.poses import Poses
from protflow.residues import ResidueSelection
from protflow.tools.rfdiffusion import RFdiffusion

poses = Poses(poses="input.pdb", work_dir="./run/")

# 1. Tag the motif in the *input* coordinates
poses.df["motif"] = poses.df.apply(
    lambda r: ResidueSelection("A12,A45,A78"), axis=1
)
poses.set_motif("motif")   # marks it; not strictly required for update_motifs

# 2. Diffuse, telling ProtFlow to re-index the motif
poses = RFdiffusion().run(
    poses,
    prefix="diff",
    options="'contigmap.contigs=[A1-100/0 50-50]'",
    update_motifs=["motif"],
)

# 3. The 'motif' column now holds the *new* indices, valid in the diffused PDB
print(poses.df[["poses_description", "motif"]])
```

## What `update_motifs` does internally

RFdiffusion writes a `.trb` file per output containing two index lists:

- `con_ref_pdb_idx`: residue indices in the *input* PDB that were kept
- `con_hal_pdb_idx`: residue indices in the *output* PDB at the equivalent positions

ProtFlow parses these into `<prefix>_con_ref_pdb_idx` and
`<prefix>_con_hal_pdb_idx` columns on `poses.df`. The
`RFdiffusion.remap_motifs(...)` step then, for each row and each motif column:

1. Looks up each `(chain, resnum)` in the motif against `con_ref_pdb_idx`.
2. Maps it to the corresponding `(chain, resnum)` in `con_hal_pdb_idx`.
3. Writes the remapped selection back to the motif column.

If the diffusion preserved a binding target (binder design), the columns
`<prefix>_complex_con_ref_pdb_idx` / `<prefix>_complex_con_hal_pdb_idx` are
used instead — they include the target indices. You don't need to choose;
RFdiffusion's runner detects which to use.

## Common patterns

### Carrying a motif through RFdiffusion → LigandMPNN → ESMFold

```python
poses.df["catalytic"] = poses.df.apply(
    lambda r: ResidueSelection("A57,A102,A195"), axis=1
)

# 1) Diffuse around the motif
poses = RFdiffusion().run(
    poses, prefix="diff",
    options="'contigmap.contigs=[10-30/A57-A57/10-30/A102-A102/10-30/A195-A195/10-30]'",
    update_motifs=["catalytic"],
)

# 2) Design while fixing the catalytic residues (they're now at *new* indices
#    in the diffused PDB, but the 'catalytic' column tracks them correctly)
poses = LigandMPNN().run(
    poses, prefix="mpnn", nseq=8, model_type="ligand_mpnn",
    fixed_res_col="catalytic",
)

# 3) Predict — ESMFold doesn't change indices, so the motif column carries through
poses = ESMFold().run(poses, prefix="esm")

# 4) Score motif identity to confirm the catalytic residues are still
#    H/D/S after design (or whatever the original residues were)
SelectionIdentity(residue_selection="catalytic",
                  onelettercode=True).run(poses, prefix="catalytic_id")
```

### Updating motifs after non-RFdiffusion structural changes

`update_motifs` is implemented by `RFdiffusion.remap_motifs`. Other runners
that change indexing (e.g. chain edits via `ChainAdder`/`ChainRemover`)
don't automatically re-map motifs — you need to either update them manually,
or apply chain edits *before* you tag motifs.

A simple manual re-mapping when you know the offset:

```python
def shift_chain(rs: ResidueSelection, chain: str, delta: int) -> ResidueSelection:
    d = rs.to_dict()
    if chain in d:
        d[chain] = [r + delta for r in d[chain]]
    return from_dict(d)

poses.df["motif"] = poses.df["motif"].apply(lambda rs: shift_chain(rs, "A", -10))
```

### Tracking motifs across multiple diffusion rounds

If you run RFdiffusion twice (e.g. backbone refinement after partial
inpainting), pass `update_motifs` to *each* call:

```python
poses = rfdiff.run(poses, prefix="diff1", options=..., update_motifs=["motif"])
poses = rfdiff.run(poses, prefix="diff2", options=..., update_motifs=["motif"])
```

After each call, the motif column is current relative to the new poses.

## Caveats

- The motif column **must** be a `ResidueSelection` (or convertible). Strings
  in a CSV-loaded campaign are re-hydrated if listed in
  `import_resselection_cols`; otherwise you must convert manually.
- RFdiffusion's contig must actually *preserve* the motif residues — if your
  contig doesn't fix them, the input residues won't appear in
  `con_ref_pdb_idx` and the remap will produce empty selections.
- For binder design with a fixed target, you usually want
  `update_motifs=[...]` even though the target's indices don't change —
  ProtFlow correctly recognises `complex_con_ref_pdb_idx` and remaps
  through that.
- `set_motif(col)` is informational only — it appends `col` to `poses.motifs`,
  which is currently used by `convert_resselection_cols` to auto-detect
  selection columns on serialisation. You do not need to call it for
  `update_motifs` to work.
