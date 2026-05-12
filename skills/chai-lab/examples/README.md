# Example inputs

Minimal copy-pasteable examples for the most common Chai-1 use cases.
Pair each FASTA with the matching command shown below.

| File | Use case |
|------|----------|
| `protein_only.fasta` | Single protein, single-sequence mode |
| `protein_ligand.fasta` | Antibody + small-molecule ligand (SMILES) |
| `antibody_antigen.fasta` | Heavy + light + antigen |
| `binder_target.fasta` | Designed binder vs target (for validation) |
| `glycoprotein.fasta` + `glycoprotein.restraints` | Glycosylated protein |
| `covalent_inhibitor.fasta` + `covalent_inhibitor.restraints` | Cys-attached covalent ligand |
| `restrained_complex.fasta` + `restrained_complex.restraints` | Two-chain complex with contact + pocket restraints |

## Commands

```bash
# Single protein
chai-lab fold protein_only.fasta out_protein_only/

# Antibody + SMILES ligand, with MSAs
chai-lab fold --use-msa-server protein_ligand.fasta out_protein_ligand/

# Antibody-antigen with MSAs + templates
chai-lab fold --use-msa-server --use-templates-server antibody_antigen.fasta out_ab_ag/

# Designed binder validation (no MSAs)
chai-lab fold --fasta-names-as-cif-chains --seed 0 binder_target.fasta out_binder/

# Glycoprotein
chai-lab fold --constraint-path glycoprotein.restraints glycoprotein.fasta out_glyco/

# Covalent inhibitor
chai-lab fold --constraint-path covalent_inhibitor.restraints covalent_inhibitor.fasta out_cov/

# Restraint-guided complex
chai-lab fold --use-msa-server --constraint-path restrained_complex.restraints \
              restrained_complex.fasta out_restr/
```

All FASTAs use placeholder sequences. Replace the `MKVLW...` style
stubs with real sequences before running.
