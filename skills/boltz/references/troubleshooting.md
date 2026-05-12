# Troubleshooting

## Installation / startup

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ImportError: libcudart.so.12` | Your CUDA driver doesn't match CUDA 12 | Install a matching driver, or `pip install boltz` (no `[cuda]` extra) for CPU-only. |
| `cuequivariance ... not compiled for sm_XX` | GPU older than what the kernels target | Add `--no_kernels` to the predict command. Small perf hit for inference. |
| `RuntimeError: Failed to download model from all URLs.` | Both `model-gateway.boltz.bio` and HuggingFace fallback unreachable | Manually download the checkpoint and place it at `<cache>/boltz2_conf.ckpt`. URLs are in `boltz.main` (`BOLTZ2_URL_WITH_FALLBACK`). |
| `ValueError: BOLTZ_CACHE must be an absolute path` | Relative path / unexpanded `~` | Use `export BOLTZ_CACHE="$(realpath ~/cache)"`. |
| First prediction hangs at "Downloading" | Large `mols.tar` (~1 GB) extraction | Wait it out; subsequent runs reuse the extracted `mols/`. |
| `boltz: command not found` after install | Console script not on PATH (venv not activated, or installed with `--user`) | Activate the venv, or `python -m boltz.main predict ...`. |

## YAML parsing

| Error | Likely cause |
|-------|--------------|
| `Invalid version 2 in input!` | Schema is at v1; remove or set `version: 1`. |
| `Invalid entity type: <foo>` | Top key of a `sequences:` item must be one of `protein`, `dna`, `rna`, `ligand`. |
| `AssertionError` in `parse_boltz_schema` near a `ligand:` entry | You declared both `smiles` and `ccd`, or neither. Pick exactly one. |
| `Bond constraint was not properly specified` | Missing `atom1` or `atom2` in a `bond:` entry. |
| `KeyError` on `(chain, residue, atom_name)` inside a bond | `RES_IDX` is wrong, atom name has wrong case, or the atom doesn't exist in the CCD entry. Verify against the RCSB CCD component CIF for that residue. |
| `Pocket constraint was not properly specified` | Missing `binder` or `contacts`. |
| `Only one pocket binders is supported in Boltz-1!` | Move to `--model boltz2` or merge into a single pocket. |
| `Max distance != 6.0 is not supported in Boltz-1!` | Set `max_distance: 6` or use Boltz-2. |
| `Contact constraint is not supported in Boltz-1!` | Use `--model boltz2`. |
| `Templates are not supported in Boltz 1.0!` | Use `--model boltz2`. |
| `Affinity prediction is only supported for Boltz2!` | Remove `properties:` or use `--model boltz2`. |
| `Binder must be a single chain.` | `properties.affinity.binder` must be a `str`, not a list. |
| `Cannot compute affinity for a ligand that has multiple copies!` | The affinity binder's `id:` is a list (e.g. `[L, M]`). Use one ligand entry. |
| `Cannot compute affinity for multi residue ligands!` | The ligand resolves to >1 residue (rare; certain large CCD codes). Split or use SMILES. |
| `The ligand for affinity is too large, ligands with more than 128 atoms ...` | Hard cap; cannot proceed. |
| `WARNING: the ligand used for affinity calculation is larger than 56 heavy-atoms` | Soft warning; affinity output is unreliable above 56 atoms. |
| `Method conditioning is not supported for Boltz-1.` | `--method` is Boltz-2 only. |
| `Method <X> not supported.` | Use one of `md`, `x-ray diffraction`, `electron microscopy`, `solution nmr`, `afdb`, `boltz-1`, etc. (case-insensitive). |
| `When providing both the chain_id and template_id, the number of template_ids provided must match the number of chain_ids!` | Lists must be equal length when both are present. |
| `Chain X assigned for template Y is not one of the protein chains!` | `chain_id` references a non-protein chain (or a typo). |
| `Template chain X assigned for template Y is not one of the protein chains!` | `template_id` references a non-protein chain in the template file. |
| `Template <id> must have threshold specified if force is set to True` | Add `threshold: <Å>` to that template entry. |

## Runtime / GPU

| Symptom | Likely cause | Fix |
|---------|-------|-----|
| `torch.OutOfMemoryError: CUDA out of memory.` | Complex too large for VRAM | `--max_parallel_samples 1`, `--max_msa_seqs 2048`, `--subsample_msa --num_subsampled_msa 512`. As a last resort, drop `--recycling_steps` to 1. |
| `NaN`/`Inf` in pLDDT or PAE | Numerics on FP16 paths; usually a transient kernel issue | Re-run with `--seed <other>`; if persistent, try `--no_kernels`. |
| Hangs at "Downloading MSA from ColabFold" | Server throttling / network blip | Wait, or run a local ColabFold (`--msa_server_url`). |
| `requests.exceptions.HTTPError 401/403` from MSA server | Auth required | Set basic auth or API key; see [msas.md](msas.md). |
| `RuntimeError: Cannot have both username/password and API key auth` | Mixed auth schemes | Pick one. |
| Process killed (OOM-killer) | RAM, not VRAM | Lower `--preprocessing-threads` and `--num_workers`. |
| Predictions silently skipped | Existing outputs found in `--out_dir` | Pass `--override` or use a different `--out_dir`. |
| DDP error `Number of requested devices is greater than the number of predictions, taking the minimum.` | Not an error — informational; Boltz reduced `--devices` to the number of inputs. | n/a |
| Very slow on CPU | Expected; CPU is 100–1000x slower than GPU | Use a GPU, or accept the wait. Don't run multi-chain or affinity on CPU. |

## Quality / accuracy

| Symptom | Likely cause | Mitigation |
|---------|-------|-----|
| Low `iptm` (<0.3) for a known interaction | Bad MSA pairing, wrong stoichiometry, wrong pocket | Try `--msa_pairing_strategy complete`; add a `pocket:` constraint; verify chain copies via `id: [A, B, ...]`. |
| Disordered loops / low pLDDT regions | Real disorder, or insufficient signal | Provide a template; add `pocket:` for known contacts; increase `--recycling_steps`. |
| Ligand floating outside the pocket | No pocket info; weak affinity signal | Add a `pocket:` constraint with `max_distance` 4–8 Å. Set `force: true` for confirmed pockets. |
| Affinity = ~0 binary, ~+2 value | Predicted non-binder | Could be correct; verify against an active control. Check `--affinity_mw_correction` for cross-chemotype comparisons. |
| Different ranking on each run | RNG seed not fixed | Pass `--seed N` for reproducibility. |
| Designed binder scores low ipTM but ipSAE is high | ipTM is more sensitive to "near miss" interfaces than ipSAE | Trust ipSAE; see the `ipsae` skill. |
| Auto-MSA hurts a designed binder | De novo binders have no useful homologs | Set `msa: empty` on the binder chain. |

## Output / parsing

| Issue | Fix |
|-------|-----|
| Missing `affinity_*.json` | Either `properties.affinity` not in YAML, or `--model boltz1`. |
| Missing `pae_*.npz` | Pass `--write_full_pae`. |
| Missing `embeddings_*.npz` | Pass `--write_embeddings`. |
| Want PDB instead of CIF | `--output_format pdb`. |
| Want per-chain pLDDT for plotting | Read `confidence_*.json["chains_ptm"]` for per-chain pTM; for per-residue pLDDT use `plddt_*.npz` and chain boundaries from the CIF. |

## Reproducibility

- Predictions are non-deterministic by default. Pass `--seed N` to fix.
- DDP scrambles input → GPU assignment based on the input set; for bit-exact reproduction predict each YAML in a separate single-GPU job.
- Different `--max_parallel_samples` may produce slightly different float ordering; keep it fixed if you compare numbers across runs.
- Model checkpoint hash:

  ```bash
  sha256sum ~/.boltz/boltz2_conf.ckpt
  ```

  Pin this in your run logs.

## Where to ask for help

- Boltz Slack — https://boltz.bio/join-slack (active maintainers).
- GitHub issues — https://github.com/jwohlwend/boltz/issues.

When reporting, attach: the input YAML (redacted as needed), the full CLI command, the `boltz` version (`pip show boltz`), and the GPU model (`nvidia-smi`).
