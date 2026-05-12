# The `Poses` Object

`protflow.poses.Poses` is the central data structure. It owns a
`pd.DataFrame` (`poses.df`) plus a working directory plus a default
JobStarter, and tracks scores across a whole campaign.

## Constructor

```python
Poses(
    poses        = None,         # str dir, str file, list[str], pd.DataFrame, or None
    work_dir     = None,         # all outputs go here; subdirs created automatically
    storage_format = "json",      # one of: json, csv, pkl/pickle
    glob_suffix  = None,          # if poses is a dir, glob with this (e.g. "*.pdb")
    jobstarter   = SbatchArrayJobstarter(),   # default for runners that don't override
)
```

What it accepts as `poses`:

| Input                                    | Behaviour                                                        |
|-------------------------------------------|-------------------------------------------------------------------|
| `None`                                   | Empty `poses.df` with the three mandatory columns                 |
| `"some/dir/"` + `glob_suffix="*.pdb"`     | Glob the directory                                                |
| `"path/to/file.pdb"`                     | Single file                                                       |
| `["a.pdb", "b.pdb"]`                     | List of files                                                     |
| `"path/to/scores.json"` (any of .json/.csv/.pkl/.parquet/.feather) | Restore a previous campaign — DataFrame is loaded as-is, including all `<prefix>_*` columns and `ResidueSelection` objects |
| `pd.DataFrame`                            | Use directly (must have `input_poses`, `poses`, `poses_description`) |
| `.fa` / `.fasta` files with multiple records | Auto-split into individual files under `work_dir/input_fastas_split/` |

## Mandatory DataFrame columns

| Column              | Meaning                                                                |
|---------------------|------------------------------------------------------------------------|
| `input_poses`        | Original input path. Never changes after construction.                 |
| `poses`              | Current "active" path. Updated by each runner that produces new files. |
| `poses_description`  | Basename without extension. Used to merge runner outputs back in.      |

Every `RunnerOutput` you merge in adds at minimum:

- `<prefix>_location` (the new file path)
- `<prefix>_description` (the new basename)
- one column per score the runner produces, named `<prefix>_<scoreterm>`

After a generative runner (RFdiffusion, LigandMPNN, …), the `poses` and
`poses_description` columns are updated to point at the *new* outputs.

## Setup / inspection methods

| Method                                        | What it does                                                |
|-----------------------------------------------|-------------------------------------------------------------|
| `set_work_dir(path, set_scorefile=True)`      | Create work_dir + the three sub-dirs (`scores/`, `filter/`, `plots/`). |
| `set_storage_format("csv"\|"json"\|...)`       | Change persistence format.                                  |
| `set_logger()`                                 | Attach a file handler under `work_dir/<basename>.log`.      |
| `set_jobstarter(JobStarter)`                   | Replace the default JobStarter.                              |
| `set_scorefile(work_dir)`                       | Recompute the canonical scorefile path.                      |
| `determine_pose_type(pose_col=None)`           | Returns the unique file extension(s) in the column.          |
| `__len__()`, `__iter__()`                       | Iterate rows or count poses.                                 |

## Inputs

| Method                                                              | What it does                                  |
|---------------------------------------------------------------------|-----------------------------------------------|
| `set_poses(poses=..., glob_suffix=...)`                              | Same input matrix as the constructor.         |
| `load_poses("path/to/scores.json")`                                  | Hydrate from a saved scorefile.               |
| `parse_poses(poses, glob_suffix=None)`                               | Returns a list[str] without mutating state.    |
| `split_multiline_fasta(path)`                                        | Used internally; writes one fa per record.     |
| `change_poses_dir(new_dir, copy=False, overwrite=False)`             | Update the `poses` column to point elsewhere.  |
| `convert_pdb_to_fasta(prefix, update_poses=False, chain_sep=":")`    | Make sequences from current poses; optionally swap into the active column. |
| `convert_resselection_cols(resselection_col="import_resselection_cols")` | After loading from CSV/JSON, re-hydrate `ResidueSelection` objects. |

## Outputs

| Method                                                              | What it does                                       |
|---------------------------------------------------------------------|----------------------------------------------------|
| `save_scores(out_path=None, out_format=None)`                        | Persist `poses.df` (auto-extension if missing).    |
| `save_poses(out_path, poses_col="poses", overwrite=True)`            | Copy current pose files to a directory.            |
| `poses_list()`                                                       | Return the list of active pose paths.              |
| `get_pose(pose_description, all_models=False)`                       | Return a `Bio.PDB.Structure`/`Model` for inspection. |

## Reshaping the campaign

| Method                                                                                       | What it does                                                                                                                  |
|----------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|
| `duplicate_poses(output_dir, n_duplicates, overwrite=False)`                                  | Replicate every row N× and copy files. Used to spawn multiple sequence designs per backbone.                                  |
| `reindex_poses(prefix, group_col=None, remove_layers=None, force_reindex=False, sep="_", overwrite=False)` | Rebuild `poses_description` after merges that introduce `_N` suffixes; strips index layers as requested.                  |
| `reset_poses(new_poses_col="input_poses", force_reset_df=False)`                              | Roll back: drop all derived rows, restore the original input. Useful when re-running a pipeline branch.                        |
| `set_motif(motif_col)`                                                                       | Mark a column as a motif column (subject to `update_motifs` remapping by RFdiffusion).                                         |

## Filtering and scoring

| Method                                                                                                | What it does                                                                                |
|-------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------|
| `filter_poses_by_rank(n, score_col, group_col=None, remove_layers=None, ascending=True, prefix=None, plot=False, plot_cols=None, overwrite=True)` | Keep top-N (or top fraction if 0 < n < 1) by `score_col`. Optionally per-group. Optionally writes a before/after density plot. |
| `filter_poses_by_value(score_col, value, operator, prefix=None, plot=False, plot_cols=None, overwrite=True, fail_on_empty=True)` | Keep rows passing `score_col <operator> value`. Operators: `<`, `<=`, `>`, `>=`, `==`, `!=`. |
| `calculate_composite_score(name, scoreterms, weights, plot=False, scale_output=False)`                | Add a composite column = weighted sum (optionally normalised). Use for ranking heterogeneous metrics. |
| `calculate_mean_score(name, score_col, skipna=False, remove_layers=None, sep="_")`                     | Aggregate a column across a layer of indexing (e.g. mean across 8 sequences per backbone). |
| `calculate_median_score`, `calculate_std_score`, `calculate_max_score`, `calculate_min_score`         | Same shape; different aggregator.                                                            |

`prefix=` in the filter methods writes a separate filtered scorefile under
`work_dir/filter/`, so you can audit any filter decision after the fact.

## On-disk layout

```
work_dir/
├── <work_dir_basename>_scores.json        ← canonical poses.df scorefile
├── <work_dir_basename>.log                ← only if set_logger() called
├── scores/                                 ← intermediate aggregated scores
├── filter/                                 ← filter audit trail
├── plots/                                  ← density / scatter plots
├── <prefix1>/                              ← runner-specific outputs
│   ├── <prefix1>_scores.json
│   ├── <jobname>_slurm.out / .err / _jobstarter.log / _cmds
│   └── output_pdbs/                        ← tool-specific subtree
├── <prefix2>/
│   └── ...
└── input_fastas_split/                     ← auto-created when a multiline fasta is passed
```

## Module-level helpers (not on `Poses`)

| Function                                                          | Use                                                                 |
|-------------------------------------------------------------------|---------------------------------------------------------------------|
| `protflow.poses.load_poses(path)`                                 | Equivalent of `Poses(poses=path)` for any saved scorefile.          |
| `protflow.poses.normalize_series(s, scale=False)`                  | Used internally by `calculate_composite_score`.                     |
| `protflow.poses.combine_dataframe_score_columns(df, scoreterms, weights, scale=False)` | Build a composite series without mutating a Poses object. |
| `protflow.poses.filter_dataframe_by_rank(df, col, n, ...)` / `filter_dataframe_by_value(df, col, value, operator)` | Pure-DataFrame versions for ad-hoc analysis. |
| `protflow.poses.col_in_df(df, col)`                                | Raises `KeyError` if missing — common runner-internal assertion.    |
| `protflow.poses.description_from_path(path)`                       | Basename without extension.                                          |
