# Integrating invrotzyme into a de novo enzyme-design pipeline

InvrotZyme is **stage 1** of a typical de novo enzyme-design pipeline.
This page sketches a canonical workflow and points at the other skills
that handle the subsequent stages.

## Canonical pipeline

```
┌──────────────────────────────────────────────────────────────┐
│ 0. Theozyme design                                           │
│    - Chemistry literature + QM transition-state geometry     │
│    - Output: Rosetta CST file + ligand .params               │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ 1. invrotzyme                                                │
│    - Enumerate clash-free catalytic rotamer assemblies       │
│    - Output: many small PDBs with REMARK 666 enzdes headers  │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. RFdiffusion All-Atom                                      │
│    - Generates a full protein backbone that hosts the        │
│      catalytic residues + ligand                             │
│    - Tool: rfdiffusion (AA flavor) - see the `rfdiffusion`   │
│      skill / heme_binder_diffusion repo                      │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. LigandMPNN / ProteinMPNN                                  │
│    - Sequence design on the new backbone, with the ligand    │
│      as conditioning and catalytic residues fixed            │
│    - Skill: `ligandmpnn`                                     │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. AF2 / Chai / Boltz refold + ligand pose                   │
│    - Validate that the designed sequence refolds to the      │
│      designed structure, with ligand in the active site      │
│    - Skills: `alphafold`, `chai`, `boltz`                    │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. Quality control + ranking                                 │
│    - Interface metrics, biophysics, ligand RMSD              │
│    - Skills: `protein-qc`, `ipsae` (for binder ranking)      │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
                       Experimental testing
```

## Sizing the invrotzyme stage

For a 4-CST theozyme with realistic Dunbrack and random subsampling
you want **hundreds to a few thousand invrotzyme outputs** going
into RFdiffusionAA. Each invrotzyme output typically produces 10–100
RFdiffusionAA backbones, of which only a small fraction survive QC.

Rule of thumb for expected attrition:

| Stage | Pass rate (very rough) |
|-------|------------------------|
| invrotzyme → RFdiffusionAA | most outputs are diffusable |
| RFdiffusionAA → MPNN | most backbones get sequence-designed |
| MPNN → refold | 20–60% pass refold (pLDDT, RMSD to designed backbone) |
| Refold → biochemical QC | 10–40% pass interface / biophysical filters |

To end up with ~50 testable designs you want **on the order of**
500–5000 invrotzyme outputs to start. Use `--max_outputs` to cap.

## Handing off to RFdiffusionAA

The canonical downstream pipeline is the **[heme_binder_diffusion](https://github.com/ikalvet/heme_binder_diffusion)**
repo, which:

- Reads the REMARK 666 lines to identify catalytic residues.
- Treats the catalytic residues + ligand as a fixed motif.
- Diffuses a new backbone (length / topology configurable) that hosts
  the motif.
- Outputs candidate scaffolds for downstream MPNN.

Two practical knobs on the invrotzyme side that matter for this
handoff:

1. **Stub length** (`--N_len`, `--C_len`). Setting both to `0` means
   *only the catalytic sidechain* is exported — RFdiffusionAA builds
   the entire scaffold around it. Larger stubs constrain the diffusion
   trajectory more tightly (the local backbone is now part of the
   motif). For *de novo* designs use `--N_len 0 --C_len 0` or very
   short stubs. For motif-grafted designs the longer stubs help the
   diffusion preserve secondary-structure context.
2. **`--tip_atom` mode**. Outputs many more PDBs, most with internal
   clashes the script didn't catch. RFdiffusionAA can still consume
   them — the clashes are typically resolved by the diffusion trajectory.
   Use `--tip_atom` when you want geometric diversity of catalytic
   placements and intend to let RFdiffusionAA do all the heavy lifting
   structurally.

## Handing off to LigandMPNN

After RFdiffusionAA produces a backbone, you'll typically:

1. Carry the original REMARK 666 lines through (or rebuild them by
   reading the CST file against the new pose) so that LigandMPNN
   knows which residues to **fix** as the catalytic identities.
2. Use the `ligandmpnn` skill's `fix_pos` flag with the catalytic
   resno list.
3. Pass the ligand by CCD code, SMILES, or include it as a het residue
   in the PDB.

## Skipping RFdiffusionAA — Rosetta enzdes path

If you instead want to use invrotzyme outputs as **matcher** outputs
for the classical Rosetta enzdes pipeline:

1. Run `python invrotzyme.py …` exactly as for the diffusion case.
2. Apply enzdes constraints to each output:
   ```bash
   rosetta_scripts.linuxgccrelease \
     -database $ROSETTA/main/database \
     -extra_res_fa lig.params \
     -enzdes::cstfile my.cst \
     -parser:protocol enzdes_design.xml \
     -in:file:s outputs/*.pdb
   ```
3. The `<AddOrRemoveMatchCsts cst_instruction="add_new"/>` mover in
   your protocol will use the REMARK 666 lines to re-instate the
   geometric constraints during minimization / design.

## Common integration footguns

- **Mismatched ligand `.params`** between invrotzyme and downstream
  steps. Use exactly the same params file end-to-end, otherwise
  atom-name conventions diverge and the REMARK lines won't match.
- **Stripping REMARK lines.** Many PDB-cleanup tools (`pdb4amber`,
  certain `pymol` save paths) drop non-standard REMARK lines. Don't
  pass invrotzyme outputs through any cleaner that touches the
  HEADER. If you must clean, preserve `REMARK 666` lines explicitly.
- **Multi-ligand REMARK ambiguity.** Single-ligand outputs reference
  the ligand as `chain X residue 0`; multi-ligand outputs use real
  chain/resno. Downstream parsers must handle both.
- **Per-CST argument lengths.** Each downstream step (RFdiffusionAA
  config, MPNN fix_pos list) needs to be re-specified against the
  *new* pose, not against invrotzyme's per-CST flags. The per-CST
  flags are an invrotzyme-only concept.
