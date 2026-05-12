# Boltz-1 vs Boltz-2

Boltz-2 is the default. Boltz-1 remains in the package for parity with the original paper and as a fallback. This doc summarises the differences so you can pick (or migrate).

## Feature matrix

| Feature | Boltz-1 | Boltz-2 |
|---------|---------|---------|
| Protein / DNA / RNA / ligand prediction | ✅ | ✅ |
| Multimers | ✅ | ✅ |
| MSA via ColabFold server | ✅ | ✅ |
| Custom `.a3m` / paired CSV MSA | ✅ | ✅ |
| `cyclic: true` polymer | ✅ | ✅ |
| `modifications:` (CCD-coded modified residues) | ✅ | ✅ |
| `constraints.bond` | ✅ | ✅ |
| `constraints.pocket` — single, `max_distance=6` only | ✅ | — |
| `constraints.pocket` — multiple, `max_distance` 4–20 | ❌ | ✅ |
| `constraints.contact` — token-token bias | ❌ | ✅ |
| `templates:` (CIF / PDB) with optional `force` | ❌ | ✅ |
| `properties.affinity` (binding affinity head) | ❌ | ✅ |
| Method conditioning (`--method`) | ❌ | ✅ |
| Inference potentials (`--use_potentials`) — "Boltz-1x" style | ✅ | ✅ |
| `cuequivariance` kernels | ✅ | ✅ |
| Default step scale | 1.638 | 1.5 |
| Pairformer blocks | 48 | 64 |

## Accuracy

- **Boltz-1**: matches or slightly trails AlphaFold-3 on the PDB benchmark; significantly above OpenFold / ESMFold on multimers.
- **Boltz-2**: surpasses AF3 and Boltz-1 on the PDB benchmark; adds affinity prediction that approaches physics-based FEP (Schrödinger FEP+) accuracy at ~1000× lower compute. See the [Boltz-2 preprint](https://doi.org/10.1101/2025.06.14.659707) for plots.

## When to use which

| Use case | Recommended |
|----------|-------------|
| Default — any structure prediction task | **Boltz-2** |
| Binding affinity (binders vs decoys, SAR ranking) | **Boltz-2** (required) |
| Templates / homology guidance | **Boltz-2** (required) |
| Multi-pocket / contact constraints | **Boltz-2** (required) |
| Reproducing the original Boltz-1 paper results | Boltz-1 (`--model boltz1`) |
| Debugging a regression you suspect is Boltz-2-specific | Boltz-1 as a sanity check |

## Migration from Boltz-1 YAML

A Boltz-1 YAML is forward-compatible with Boltz-2 — you can leave `--model boltz2` (the default) and it just works. Things you can now add:

```yaml
# Before (Boltz-1): single pocket, 6 Å only
constraints:
  - pocket:
      binder: B
      contacts: [[A, 138]]

# After (Boltz-2): multiple pockets at varying distances
constraints:
  - pocket:
      binder: B
      contacts: [[A, 138]]
      max_distance: 8
  - pocket:
      binder: C
      contacts: [[A, 200], [A, 205]]
      max_distance: 5

# After (Boltz-2): contact constraints
  - contact:
      token1: [A, 42]
      token2: [B, 1]
      max_distance: 4

# After (Boltz-2): templates
templates:
  - cif: ./template.cif

# After (Boltz-2): affinity
properties:
  - affinity:
      binder: B
```

If you migrate a script that called Boltz-1 explicitly, drop `--model boltz1` to switch to Boltz-2 and adjust the default `--step_scale` expectation (1.638 → 1.5 — but only matters if you tuned it explicitly).

## Internals (for the curious)

- Different `Pairformer` configurations: 48 blocks (Boltz-1) vs 64 blocks (Boltz-2), both with 16 heads.
- Different `DiffusionParams` defaults: Boltz-2 has lower `gamma_0` (0.8 vs 0.605), higher `noise_scale` (1.003 vs 0.901), and a smaller `step_scale` (1.5 vs 1.638), `rho` of 7 vs 8.
- Reference structures: Boltz-2 ships a `mols/` directory (extracted from `mols.tar`); Boltz-1 ships `ccd.pkl`.
- Affinity head: extra checkpoint `boltz2_aff.ckpt`, with its own diffusion-sample count (`--diffusion_samples_affinity`, default 5).
- Method conditioning: Boltz-2 takes a one-hot method id and biases the trunk featurisation accordingly (allowed values in `boltz.data.const.method_types_ids`).
