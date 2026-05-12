# Taming combinatorial explosion

The number of rotamer combinations evaluated by invrotzyme is the
product of the per-CST pool sizes:

```
N_total = N_ligand × N_cst1 × N_cst2 × … × N_cstK
```

Per-residue Dunbrack pools easily reach 50–200 rotamers, so a 4-CST
problem with default settings sees 10⁷–10⁸ combinations. This page
lists the levers, ordered by how much they cut the search and by how
much physical content they preserve.

## Layered filtering — recipe

The script applies filters in this order; design your invocation
around that order:

1. **Per-CST Dunbrack probability cutoff** — drops low-probability
   rotamers entirely.
2. **`SECONDARY_MATCH` driven per-CST secondary structure restriction**
   — limits the Dunbrack pool to (φ, ψ) bins consistent with the
   chosen stub secondary structure (`H`/`E`).
3. **Proton-χ pruning** — `protocol.prune_residue_rotamers` removes
   duplicates differing only in `chi_proton`.
4. **Per-CST `use_best_rotamer_cstids`** — keeps only the single best
   rotamer per SS bin for the listed CSTs.
5. **Ligand-rotamer RMSD pruning** — `prune_ligand_rotamers` collapses
   geometrically similar ligand conformers.
6. **Extra-χ sub-sampling** — *expands* the pool with deterministic
   ± nσ samples per χ.
7. **Random subsampling** — `max_random_rotamers*` (caps) or
   `frac_random_rotamers*` (fractions).
8. **`itertools.product`** of the surviving per-CST pools.

Per-residue **clash failures memoize** into a `bad_rotamers` list
shared across workers — a rotamer that clashes once is skipped in
every subsequent combination. This caches a lot of work, but only
helps if the bad rotamer is hit *early* in the enumeration; the
random subsampler is your friend here.

## Leverage table

| Lever | Typical reduction | Physical cost |
|-------|-------------------|---------------|
| `--dunbrack_prob 0.5–0.6` (default 0.85) | 5–10× per CST | Loses long-tail rotamers — usually fine for theozymes |
| `--secstruct_per_cst H E …` | 2–3× per CST | Mandatory if you have a target SS for the stub |
| `--use_best_rotamer_cstids` (per CST) | 5–50× | Locks you into the SS-bin mode — diversity drops |
| `--frac_random_rotamers_per_cst 0.3 …` | 3.3× per CST | Random — diversity preserved, just sparser |
| `--max_random_rotamers_per_cst 5 …` | 10–50× per CST | Same as fraction but absolute. Tractable for prototyping |
| `--prune_ligand_rotamers 0.5` (RMSD Å) | 2–10× on ligand | Removes near-duplicates only |
| `--keep_his_tautomer '1:HIS'` | 2× on that CST | Locks chemistry |
| `--max_outputs N` | early-stop | Doesn't reduce the search — caps the output |
| `--tip_atom` | massive | Skips clash check — most outputs will need re-checking |

## Recommended starting points

### "I just want to see if this CST is feasible" (10 minutes on 32 cores)

```
--dunbrack_prob 0.6
--frac_random_rotamers_per_cst 0.3 0.3 0.3 0.3   (ligand + 3 CSTs)
--max_outputs 200
```

If `--max_outputs` triggers early, the assembly space is rich and you
can dial down the randomness or raise the Dunbrack cutoff.

### "I want a thorough but tractable enumeration" (hours)

```
--dunbrack_prob 0.7
--frac_random_rotamers_per_cst 0.5 0.7 0.7 0.7
--prune_ligand_rotamers 0.5
```

Keep ligand-rotamer fraction lower than residue fractions — the
ligand multiplies into every other pool, so each ligand rotamer is
already getting a lot of search.

### "I'm running an exhaustive sweep" (days, big machine)

```
--dunbrack_prob 0.9
--prune_ligand_rotamers 0.3
--max_outputs 50000
```

Pair this with sharding across multiple SLURM jobs (different
`--prefix outputs/shard_<i>_`) — invrotzyme has no built-in shard
flag, but running disjoint configs in parallel is the simplest path.

## When `--use_best_rotamer_cstids` makes sense

`use_best_rotamer_cstids` keeps **only one rotamer per (residue type,
SS bin)** for the listed CSTs. Two situations where it pays off:

1. **The CST geometry is so tight that subsampling won't open new
   solutions.** A buried H-bond donor with `±5°` torsion windows will
   typically converge to the same handful of χ values regardless of
   the Dunbrack tail.
2. **You're using `--secstruct_per_cst` and just want the canonical
   helical/strand-favored rotamer.** This cuts the per-CST pool to
   1–3 rotamers and makes the combinatorial space dominated by the
   ligand and the *other* CSTs.

Don't use it on the most ligand-distal residue — that's typically
where geometric variety matters most.

## When `--tip_atom` makes sense

`--tip_atom` flips the script from a clash-driven enumerator into a
**geometric-diversity** enumerator:

- Pre-selects rotamers by whether they place the catalytic tip atom
  in a geometrically distinct location.
- Skips most pairwise clash checks.
- Outputs many more PDBs, most of which **will** clash in a real
  scaffold.

Use it when the downstream consumer (RFdiffusionAA, etc.) is going to
rebuild the backbone anyway and you only need a set of candidate
catalytic-atom placements. Don't use it if you intend to use the
output directly for Rosetta enzdes or for any pipeline that does not
relax / rebuild the backbone.
