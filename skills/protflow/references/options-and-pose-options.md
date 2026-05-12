# `options` vs `pose_options` vs `pose_opt_cols`

ProtFlow runners accept three flavours of configuration that all map to a
tool's CLI invocation. They compose; pose-level values override global values
on key conflicts.

## `options` — global, string

```python
runner.run(poses, prefix="x", options="--temperature 0.05 --seed 1")
```

Passed to every pose, verbatim, in the tool's native CLI syntax. The separator
the runner uses to parse this string varies by tool:

| Runner                                           | Separator | Notes                                                |
|--------------------------------------------------|-----------|------------------------------------------------------|
| LigandMPNN, ESMFold, ESM, ColabFold, AlphaFold3, Boltz, ...  | `--`      | Standard. `--key value` or `--key=value`.            |
| RFdiffusion / RFdiffusion3                       | whitespace (regex, quote-aware) | Hydra-style `key=value`, e.g. `'contigmap.contigs=[70-70]'`. Quote complex values. |
| Rosetta                                          | `-`       | Rosetta CLI uses single dashes; some keys take `:`.   |

When in doubt, copy the string you'd type on the command line. ProtFlow's
parser is intentionally lenient (`regex_expand_options_flags` is quote-aware).

## `pose_options` — per-row, unstructured string

```python
poses.df["mpnn_opts"] = ["--fixed_residues 'A12 A34'", "--fixed_residues 'A56'", None]
runner.run(poses, prefix="mpnn", pose_options="mpnn_opts", options="--temperature 0.1")
```

Three forms accepted:

1. **String**: a `poses.df` column name. Cells must be strings (or `None`).
2. **List**: a list of strings the same length as `len(poses)`. The runner
   matches them to rows in order.
3. **None**: equivalent to a list of all `None`.

Per-pose values override global `options` where keys conflict.

## `pose_opt_cols` — per-row, structured

```python
poses.df["fixed_residues"] = [ResidueSelection("A12,A34"), ResidueSelection("A56"), ResidueSelection("")]
runner.run(poses, prefix="mpnn", pose_opt_cols={"fixed_residues": "fixed_residues"})
```

A dict from the *tool's CLI flag* → the *poses.df column name* whose cells
hold the values. The runner is responsible for serialising each cell.
LigandMPNN, AlphaFold3, and a few others support this; it's the right shape
for `ResidueSelection`, paths, or any value that doesn't round-trip cleanly
through a CLI string.

LigandMPNN ships two convenience shortcuts that populate `pose_opt_cols` for
you:

```python
ligandmpnn.run(poses, prefix="x", fixed_res_col="active_site")     # == pose_opt_cols={"fixed_residues": "active_site"}
ligandmpnn.run(poses, prefix="x", design_res_col="designable")     # == pose_opt_cols={"redesigned_residues": "designable"}
```

## How the three layers compose

For runners that support all three (e.g. LigandMPNN), the order is:

```
1. options                                  # baseline
2. pose_opt_cols[col] → serialised string   # overrides on conflict
3. pose_options[i]                          # overrides on conflict
```

The runner internally calls `parse_generic_options(options, pose_opts, sep=...)`
which merges into `(opts: dict, flags: set)` and serialises back via
`options_flags_to_string`. So you can pass overlapping keys; the rightmost
source wins.

## Tool-specific cheatsheet

### LigandMPNN (`--`-separated)

Global options that almost always apply to a campaign:

```python
options = "--temperature 0.1 --seed 1 --batch_size 8"
```

Useful CLI flags:

| Flag                                  | Meaning                                                                  |
|---------------------------------------|---------------------------------------------------------------------------|
| `--temperature`                       | Sampling temperature (0.05–0.2 typical).                                  |
| `--batch_size`                        | Sequences per GPU pass.                                                    |
| `--seed`                              | RNG seed.                                                                  |
| `--checkpoint_*` (set by `model_type` kwarg) | Don't set manually; use the `model_type` kwarg.                    |
| `--bias_AA "A:1.0,G:-0.5"`            | Per-amino-acid sampling bias.                                              |
| `--pack_side_chains 1`                | Run sidechain packing on outputs.                                          |

Per-pose: prefer `pose_opt_cols={"fixed_residues": col, "redesigned_residues": col, "omit_AA_per_residue": col}`
over hand-formatted strings.

### RFdiffusion (Hydra-style, whitespace-separated)

Examples (note shell quoting):

```python
options = "'contigmap.contigs=[A1-100/0 70-70]' 'ppi.hotspot_res=[A42,A45,A82]'"
```

| Key                                       | Meaning                                                            |
|-------------------------------------------|---------------------------------------------------------------------|
| `contigmap.contigs=[...]`                 | Contig string. Specifies which residues to keep / inpaint / sample. |
| `inference.input_pdb=...`                 | Input PDB. ProtFlow sets this for you when poses are provided.       |
| `inference.num_designs=N`                 | Equivalent to ProtFlow's `num_diffusions` kwarg (don't double-set).  |
| `inference.output_prefix=...`             | Output prefix. Set by ProtFlow.                                       |
| `ppi.hotspot_res=[...]`                   | Hotspot residues for binder design.                                  |
| `denoiser.noise_scale_ca=N`               | Noise level for CA atoms.                                             |
| `potentials.guiding_potentials=[...]`     | Symmetry / shape potentials.                                          |

Always quote contig strings with single quotes — the brackets break shells
otherwise.

### AlphaFold3

```python
options = "--flash_attention_implementation xla --cuda_compute_7x 1 --num_recycles 10"

additional_entities = {"ligand": {"id": "Z", "smiles": "CCO"}}
# or, per pose:
poses.df["lig"] = [{"id": "Z", "smiles": s} for s in smiles_list]
af3.run(poses, prefix="af3", col_as_input=True, additional_entities="lig")
```

### Rosetta (single-dash)

```python
options = "-relax:fast -relax:constrain_relax_to_start_coords -ex1 -ex2"
rosetta.run(poses, prefix="relax", rosetta_application="relax.linuxgccrelease",
            nstruct=5, options=options)
```

For RosettaScripts:

```python
options = "-parser:protocol my_protocol.xml -parser:script_vars target=A"
rosetta.run(poses, prefix="script",
            rosetta_application="rosetta_scripts.linuxgccrelease",
            options=options)
```

### ESM

Use the `include=[...]` kwarg instead of `--include` in `options`. Allowed
values: `{mean, per_tok, bos, contacts, logits, logprobs, perres_probabilities,
perres_entropy, mean_entropy}`.

```python
esm.run(poses, prefix="esm", include=["mean", "perres_entropy"])
```

## Gotchas

- **`options` is the *tool's* native flag syntax, not ProtFlow's**. ProtFlow
  doesn't validate the contents — typos surface as tool-level errors (visible
  in the stderr tail).
- **Don't set keys ProtFlow already controls**: `inference.input_pdb`,
  `inference.output_prefix`, `inference.num_designs` for RFdiffusion; sbatch
  `--array` / `-J`; etc.
- **Quoting in shell-bound strings**: contig strings, SMILES, dict-like
  Hydra values almost always need single quotes around the *value*, double
  quotes around the whole option, e.g. `"'contigmap.contigs=[70-70]'"`.
- **`pose_options` cells of `None` are valid**: they fall back to global
  `options`. Use this to give *some* poses extra constraints without
  duplicating the base config.
- **Length mismatch**: `Runner.prep_pose_options` raises `ValueError` if a
  passed list isn't the same length as `len(poses)`. If you've duplicated
  poses with `poses.duplicate_poses(...)`, refresh the list afterwards.
