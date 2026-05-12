# invrotzyme — example invocations

The invrotzyme repo ships two worked examples under
`<invrotzyme>/examples/`. Each contains an `inputs/` directory and a
`command` file with the canonical invocation.

| Example | Path in repo | Catalytic motif |
|---------|--------------|-----------------|
| Kemp eliminase | `examples/Kemp_eliminase/` | HIS-(GLU/ASP) dyad + (SER/THR/TYR/ASN/GLN) oxyanion hole around a benzisoxazole substrate. |
| P450 | `examples/P450/` | CYS heme-coordinating motif (sourced from a P450 structure) + substrate-positioning H-bond. |

This directory mirrors the two example commands and adds three
additional invocation patterns that come up frequently. To run any
of them, you need a checkout of `~/Repos/invrotzyme` (or wherever) and
the corresponding input files under that repo's `examples/`.

---

## kemp_eliminase.sh — published example, HHE backbone bins

```bash
cd <invrotzyme>/examples/Kemp_eliminase
python ../../invrotzyme.py \
  --cstfile inputs/BIO_His_ED_oxy_nosample.cst \
  --params  inputs/BIO.params \
  --dunbrack_prob 0.6 \
  --frac_random_rotamers_per_cst 0.5 0.5 0.5 0.5 \
  --secstruct_per_cst H H E \
  --prefix outputs/ \
  --suffix HHE
```

Three CSTs (HIS, GLU/ASP, oxyanion donor). Per-CST fractions:
**ligand-first** (`0.5 0.5 0.5 0.5` = 4 entries for 1 ligand + 3 CSTs).
Per-CST SS list: **ligand-excluded** (`H H E` = 3 entries).

---

## p450_with_motif.sh — fix one catalytic residue via external motif

```bash
cd <invrotzyme>/examples/P450
python ../../invrotzyme.py \
  --cstfile inputs/HBA_CYS_P450_nosample.cst \
  --params  inputs/HBA_unique.params \
  --motif_for_cst 1:3:inputs/P450_motif.pdb \
  --frac_random_rotamers 0.1 \
  --prefix outputs/
```

`--motif_for_cst 1:3:inputs/P450_motif.pdb` pins residue 3 of the
motif PDB as the catalytic CYS for CST 1. Scalar
`--frac_random_rotamers 0.1` applies 10% random subsampling to all
CSTs (no per-CST list needed).

---

## quick_feasibility.sh — minutes, just answer "is this CST feasible?"

```bash
python <invrotzyme>/invrotzyme.py \
  --cstfile  my.cst \
  --params   lig.params \
  --dunbrack_prob 0.6 \
  --frac_random_rotamers_per_cst 0.3 0.3 0.3 0.3 \
  --max_outputs 200 \
  --prefix outputs/feasibility_
```

If `--max_outputs 200` triggers, your assembly space is rich; loosen
random subsampling and raise Dunbrack. If you get zero outputs, run
again with `--debug` to find which stage rejects everything.

---

## diffusion_input.sh — produce RFdiffusionAA-ready inputs (no stubs)

```bash
python <invrotzyme>/invrotzyme.py \
  --cstfile rich.cst \
  --params  lig.params \
  --N_len 0 --C_len 0 \
  --tip_atom \
  --dunbrack_prob 0.9 \
  --prune_ligand_rotamers 0.5 \
  --prefix outputs/diffusion_input_
```

- `--N_len 0 --C_len 0` strips stubs — only the catalytic sidechains
  appear in each output.
- `--tip_atom` widens the output set by skipping pairwise clash checks.
- Aimed at downstream RFdiffusionAA, which rebuilds the backbone
  regardless.

---

## exhaustive_sweep.sh — overnight, get every feasible assembly

```bash
python <invrotzyme>/invrotzyme.py \
  --cstfile rich.cst \
  --params  lig.params \
  --dunbrack_prob 0.95 \
  --prune_ligand_rotamers 0.3 \
  --max_outputs 50000 \
  --secstruct_per_cst H H E \
  --N_len 4 --C_len 5 \
  --prefix outputs/sweep_
```

No random subsampling. Tight ligand-rotamer dedup. Output capped at
50 000. Expect overnight on 32–64 cores; pair with SLURM and let
`SLURM_CPUS_ON_NODE` set `--nproc` automatically.
