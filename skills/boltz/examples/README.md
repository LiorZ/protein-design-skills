# Examples

Drop-in YAML inputs for `boltz predict`. Replace `<REPLACE_WITH_*>` placeholders with real sequences before running.

| File | What it shows |
|------|---------------|
| `monomer.yaml` | Simplest case — one protein chain. |
| `multimer.yaml` | Heterodimer (two distinct chains). |
| `homodimer_with_ligands.yaml` | Homodimer (`id: [A, B]`) + CCD ligand + SMILES ligand, each with two copies. |
| `pocket.yaml` | Bias a CCD ligand into a known pocket via a `pocket:` constraint. |
| `affinity.yaml` | Boltz-2 binding-affinity prediction (`properties.affinity.binder`). |
| `cyclic_peptide.yaml` | Head-to-tail cyclic peptide (`cyclic: true`). |
| `custom_msa.yaml` | Use a local `.a3m` instead of the ColabFold server. |
| `no_msa.yaml` | Single-sequence mode (`msa: empty`) — for de novo designs. |
| `modified_residue.yaml` | Modified residues via CCD codes (e.g. MSE, SEP). |
| `covalent_bond.yaml` | Explicit covalent bond between a CCD ligand and a protein side chain. |
| `with_template.yaml` | Boltz-2 template-guided prediction (CIF / PDB, optional force). |
| `contact_constraint.yaml` | Boltz-2 token-token contact bias (e.g. from cross-linking MS). |
| `dna_rna_protein.yaml` | Mixed protein / DNA / RNA complex. |
| `binder_validation.yaml` | Cross-validate a designed binder against a target. |

Run any of them with:

```bash
boltz predict examples/<file>.yaml --use_msa_server
```

For details on the YAML schema, see `../references/inputs.md`.
