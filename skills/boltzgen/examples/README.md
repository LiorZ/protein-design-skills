# Example YAML specifications

Each file is a self-contained, fully commented design spec. They are
designed to be copy-paste templates rather than runnable as-is (you'll
need to supply real CIF files for the target).

Recommended workflow for each:

```bash
# 1. Replace the placeholder target file path with your own CIF / PDB.
# 2. Validate
boltzgen check examples/<file>.yaml
# 3. Open the resulting cif in https://molstar.org/viewer/ — verify the
#    binding site, designed regions, and structure-group visibility.
# 4. Pilot run
boltzgen run examples/<file>.yaml --output workbench/test --num_designs 50 [--protocol …]
# 5. Production run
boltzgen run examples/<file>.yaml --output workbench/prod --num_designs 30000 [--protocol …]
```

| File                                  | Protocol                    | Highlights                                                           |
|---------------------------------------|-----------------------------|----------------------------------------------------------------------|
| `vanilla_protein_binder.yaml`         | `protein-anything`          | Minimal design — variable-length protein vs. a chain                  |
| `protein_with_binding_site.yaml`      | `protein-anything`          | Specific binding-site residues                                       |
| `peptide_with_binding_site.yaml`      | `peptide-anything`          | Linear peptide vs. a specific site                                   |
| `cyclic_peptide.yaml`                 | `peptide-anything`          | Head-to-tail cyclic peptide                                          |
| `disulfide_peptide.yaml`              | `peptide-anything`          | Multi-disulfide peptide + secondary-structure conditioning           |
| `helicon_with_staple.yaml`            | `peptide-anything`          | Helical peptide stapled via the WHL small molecule                   |
| `cyclotide.yaml`                      | `peptide-anything`          | Cyclic peptide with three disulfide bridges                          |
| `nanobody.yaml`                       | `nanobody-anything`         | Nanobody CDR design with a scaffold-library file list                |
| `nanobody_scaffold.yaml`              | (referenced)                | A single nanobody scaffold (the file-shaped inner YAML)              |
| `antibody_fab.yaml`                   | `antibody-anything`         | Fab heavy+light CDR design with a scaffold library                   |
| `antibody_fab_scaffold.yaml`          | (referenced)                | A single Fab scaffold inner YAML                                     |
| `protein_against_small_molecule.yaml` | `protein-small_molecule`    | Protein binder vs. a SMILES ligand                                   |
| `small_molecule_via_ccd.yaml`         | `protein-small_molecule`    | Protein binder vs. a CCD-coded ligand                                |
| `covalent_small_molecule.yaml`        | `protein-anything`          | Covalent chemistry — bonds to atoms from both CCD and SMILES         |
| `zinc_finger_against_dna.yaml`        | `protein-anything`          | De novo zinc finger redesigned against B-DNA                          |
| `disordered_target.yaml`              | `protein-anything`          | Bind a disordered region of a target (hide structure with visibility 0) |
| `disordered_peptide_as_string.yaml`   | `protein-anything`          | Bind a fixed peptide passed as a sequence (no CIF)                   |
| `flexible_target_assembly.yaml`       | `protein-anything`          | Biological-assembly target + hidden flexible loops                   |
| `redesign_symmetric_dimer.yaml`       | `protein-redesign`          | Sequence redesign with `symmetric_group` tying chains                 |
| `inverse_folding_only.yaml`           | (use `--only_inverse_fold`) | IF an existing complex (replace ProteinMPNN)                          |
| `residue_constraints.yaml`            | `protein-anything`          | Per-position whitelist / blacklist of amino acids                     |
| `design_spec_kitchen_sink.yaml`       | `protein-anything`          | One file demonstrating every YAML feature                             |
