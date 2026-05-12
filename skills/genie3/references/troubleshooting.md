# Troubleshooting

A grab-bag of failure modes, what triggers them, and how to fix.

## CLI / env failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| `genie3: command not found` | Env not activated | `conda activate genie3` |
| `genie3 executable not found on PATH` (from `genie3 run`) | Same, but inside a subprocess | Activate env in the parent shell; the child inherits PATH |
| `argparse` error: shard-id out of range | Forgot to set `--num-shards` (defaults to 1) | Pass both `--shard-id` and `--num-shards`; ensure `0 ≤ shard_id < num_shards` |
| Crash with no traceback in terminal | Default mode hides per-stage logs | Re-run with `--verbose`, or read `logs/runs/<latest>/run.log` |
| Pre-existing process on GPU | OOM at startup | `nvidia-smi`, kill the stragglers; Genie 3 frees memory between stages but not between processes |

## Config errors (`ConfigError`)

| Message | Cause | Fix |
|---------|-------|-----|
| "Conflicting output directories" | Both `paths.rootdir` and `paths.outdir` (or `generation.io.outdir`) set with different values | Use only `paths.rootdir` |
| "`generation.dataset.datadir` is no longer supported" | Set `datadir` under `generation.dataset` | Move to `paths.dataset` |
| "`reward.reward.datadir` is no longer supported" | Same, in beam-search reward block | Use `paths.dataset` |
| "Use either `generation.sampler` or `generation.inference.sampler`" | Set both shorthands | Pick one (the loader keeps `inference.sampler`) |
| "Missing required config field: `evaluation.version`" | Forgot to pick a reducer | Set `evaluation.version: <unconditional|scaffold|binder>` |
| "Missing evaluation root directory" | No `paths.rootdir` for `evaluate` | Set `paths.rootdir` |
| "Missing required config section: `generation`" | Running `generate` or `run` without a `generation:` block | Add it |
| "`rounds[i].cond_strategy` is required" | Empty or missing `cond_strategy` in iterative round | Set one |

## Generation issues

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| All samples have `scrmsd` ≫ 2 | `direction_scale` too low for length | See [configuration.md#sampler-direction-scale-cheat-sheet](configuration.md#sampler-direction_scale-cheat-sheet) |
| All samples look identical | `direction_scale` too high (mode collapse) | Lower it; sweep `0.0 / 0.4 / 0.8` |
| OOM during generation at long lengths | VRAM pressure | Lower `dataset.batch_size` to 1 (default), reduce concurrent workers, use smaller GPUs |
| `torch.compile` warmup hangs / fails | Compile path not warm | Run with `compile: false` first; only enable for beam search |
| Beam search produces too few samples | Misunderstood `n_sample` semantics in beam mode | `n_sample` is *total designs*; auto-divided by `beam_width`. See [iterative-and-beam.md](iterative-and-beam.md) |
| Iterative round skipped unexpectedly | `.generate_done` and `.evaluate_done` exist | Delete sentinels for the round you want to re-run |
| Iterative `iter_common*` warning "No successes found" | Round 0 had no V0 hits | Switch that round to `extended` or `common`; or increase `n_sample` |

## Evaluation issues

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| ColabFold OOM | `num_models` too high for VRAM | Lower `evaluation.folding.num_models` (default 5); use `template` mode (no MSA) |
| ColabFold weights not found | `XDG_CACHE_HOME` differs between nodes | Re-run `setup.sh` on the node, or sync `~/.cache/colabfold` |
| ESMFold fails at import | GCC toolchain not active | Re-activate env so `esmfold_env.sh` runs; check `CC=$CONDA_PREFIX/bin/x86_64-conda-linux-gnu-gcc` |
| Reduce step writes empty `info.csv` | Some shard markers missing | `genie3 status -c <CFG>`; re-run missing shards before reduce |
| Reduce step won't re-run | `eval.done` sentinel present | Delete `<problem>/results/eval.done` |
| `ipsae` import error | IPSAE clone missing | Re-run `setup.sh`'s `install_ipsae` step or `git clone` manually into `packages/IPSAE` |
| FoldSeek not found | Not installed in env | `conda install -c conda-forge -c bioconda foldseek` (or re-run setup) |
| `mkdssp` not found | Not built | Re-run `setup.sh`'s `install_dssp` step |

## Binder problem prep failures (`prepare.py`)

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Output directory existed: <path>` | Re-running prep into the same path | `rm -rf <outdir>/<config.name>` first, or pick a fresh name |
| `Missing hotspots: A65, A93` | Hotspot tags don't match CA atoms in the PDB | Verify PDB chain IDs and residue numbers; clean PDB first if needed |
| `Current version does not support insertion code or alternative locations` | PDB has altlocs (col 17) or insertion codes (col 27) | Pre-filter with e.g. `pdb_selaltloc -A target.pdb > clean.pdb` |
| `Missing residues in pdb sequence requires full sequence specified` | Gaps in PDB without a `sequence:` provided | Add `sequence:` for that chain in the config YAML |
| `Mismatch between pdb sequence and full sequence` | Provided full sequence doesn't align to PDB-derived sequence | Recheck the FASTA you pasted — it must match the structure |
| `colabfold_batch` MSA call hangs | Network down or MSA server overloaded | Wait and retry; or pre-compute MSAs and place them at the expected paths |
| `Specified full sequence is shorter than pdb sequence` | The provided sequence omits trailing residues present in the PDB | Provide the complete sequence including the C-terminus |

## Output / metric anomalies

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `complex_scrmsd_mode == binder_only` | ColabFold's complex didn't align to the target → fell back to binder-only Cα RMSD | Investigate the `successful_complexes/` PDB — may indicate target unfolding |
| All `target_hotspot_coverage == 0` | Hotspots are on the wrong chain in the problem JSON | Inspect `<dataset>/problems/<key>.json` |
| Binder cluster CSV empty | No V0 successes; clustering only runs on the success set | Loosen `direction_scale`, switch to `cond_strategy: extended`, or increase `n_sample` |

## Performance / cost surprises

- **`evaluation.inverse_folding.num_seq` defaults to 8** — that's 8× more ColabFold predictions than necessary for screening. Set to `1` unless you need sequence diversity per backbone.
- **`evaluation.folding.num_models` defaults to 5** — 5× more compute than `num_models: 1`. Use 1 for screening, 5 only for final candidates.
- **`folding.mode: msa`** is roughly 2× slower than `template` because of MSA generation per design. Use `template` unless target structure is poor.
- **Beam search compounds**: `beam_width=4, score_interval=25` means ColabFold runs ~T/25 times per beam-search trajectory, where T is the diffusion step count. Roughly 8–12 ColabFold calls per output.

## When in doubt

1. Run `genie3 status -c <CFG>` to see exact pipeline state.
2. Tail the latest log: `tail -f logs/runs/<latest>/run.log`.
3. Re-run the failing stage with `--verbose` for live output.
4. For clean re-runs, delete the sentinel files (`.shard_markers/*`, `.generate_done`, `.evaluate_done`, `eval.done`) for the stages you want to repeat.
