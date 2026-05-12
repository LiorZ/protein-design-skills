# The Runner Pattern

Every runner subclasses `protflow.runners.Runner`. The base class enforces a
small contract; everything else is the runner's choice.

## The contract

```python
class MyTool(Runner):
    def __init__(self, jobstarter=None, **tool_specific):
        # Resolve config paths via require_config() + load_config_path().
        # Store jobstarter as self.jobstarter (may be None).
        # Set self.index_layers = how many '_N' suffixes the tool adds per pose.
        ...

    def __str__(self) -> str:
        return "mytool"          # used in log messages

    def run(self, poses, prefix, jobstarter=None, ...) -> Poses:
        # Mandatory shape: returns the same Poses, mutated.
        ...
```

The base class provides:

| Helper                                                                                                                                                       | What it does                                                                                                          |
|--------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------|
| `generic_run_setup(poses, prefix, jobstarters, make_work_dir=True)`                                                                                          | Validates prefix; resolves jobstarter from the three-element priority list; creates `poses.work_dir/<prefix>/`; stores `self.current_jobstarter`. Returns `(work_dir, jobstarter)`. |
| `check_for_prefix(prefix, poses)`                                                                                                                            | Raises if `{prefix}_location` or `{prefix}_description` already exists in `poses.df`.                                |
| `check_for_existing_scorefile(scorefile, overwrite=False)`                                                                                                   | Returns a hydrated DataFrame if the score file exists *and* `overwrite=False`; else `None`. Enables idempotent reruns. |
| `prep_pose_options(poses, pose_options=None)`                                                                                                                | Normalises `pose_options` (list, column name, or None) to a list of length `len(poses)`.                              |
| `save_runner_scorefile(scores, scorefile)`                                                                                                                   | Persists a DataFrame to the right format based on file extension.                                                     |
| `search_path(path, name, is_dir=False)`                                                                                                                       | Validates a config-derived path; raises with a useful message if missing.                                              |
| `Runner.CrashError`                                                                                                                                          | The exception type re-raised when `collect_scores(...)` fails, with the stderr tail attached.                          |

The base class also installs `__init_subclass__` magic that wraps every
subclass's `run()` with `_wrap_run_with_stderr_context`. That wrapper:

1. Lets exceptions through unchanged unless they originated inside
   `collect_scores()` (or `ProcessError` for `LocalJobStarter`).
2. For those, attaches the last 16 KiB of `self.current_jobstarter.last_error_message`
   to a new `Runner.CrashError`, preserving the original via `__cause__`.

This is the single most important debugging affordance ProtFlow provides.

## The RunnerOutput wrapper

After your runner gathers a DataFrame of results, you wrap and merge:

```python
return RunnerOutput(
    poses=poses,
    results=scores,                # must have 'description' + 'location' + score cols
    prefix=prefix,
    index_layers=self.index_layers,   # how many '_N' suffixes to strip when matching
    index_sep="_",
).return_poses()
```

What `RunnerOutput.return_poses` does:

1. Validates that `description` matches `os.path.splitext(os.path.basename(location))[0]`.
2. Strips `index_layers` suffixes from `description` to compute a `select_col`
   that joins against `poses.df['poses_description']`.
3. Renames every results column to `{prefix}_<col>`.
4. Inner-joins on `poses_description == {prefix}_select_col`.
5. Updates `poses` and `poses_description` to the new locations + descriptions.
6. Saves the updated `poses.df` to the canonical scorefile.

`index_layers` matters: a sequence-design tool that produces 8 sequences per
backbone typically appends `_0001`–`_0008` to the description. Set
`index_layers=1` and the merge collapses all 8 children back onto the single
parent row before fanning out.

## Three annotated examples

### 1. `BackboneRMSD` — a metric runner with no SLURM

This runs entirely in-process; no jobstarter, no commands. Pattern:

```python
class BackboneRMSD(Runner):
    def __init__(self, ref_col=None, atoms=["CA"], chains=None, overwrite=False, jobstarter=None):
        self.ref_col = ref_col
        self.atoms = atoms
        self.chains = chains
        self.overwrite = overwrite
        self.jobstarter = jobstarter
        self.index_layers = 0

    def __str__(self):
        return "backbone_rmsd"

    def run(self, poses, prefix, ref_col=None, jobstarter=None, chains=None, overwrite=False):
        ref_col = ref_col or self.ref_col
        chains = chains or self.chains
        work_dir, _ = self.generic_run_setup(poses=poses, prefix=prefix,
                                             jobstarters=[jobstarter, self.jobstarter, poses.default_jobstarter])
        scorefile = f"{work_dir}/{prefix}_scores.{poses.storage_format}"
        if (scores := self.check_for_existing_scorefile(scorefile, overwrite)) is not None:
            return RunnerOutput(poses, scores, prefix, index_layers=self.index_layers).return_poses()

        # compute in-process
        rows = [_compute_rmsd(row["poses"], row[ref_col], self.atoms, chains) for _, row in poses.df.iterrows()]
        scores = pd.DataFrame({
            "description": poses.df["poses_description"],
            "location": poses.df["poses"],
            "rmsd": rows,
        })
        self.save_runner_scorefile(scores, scorefile)
        return RunnerOutput(poses, scores, prefix, index_layers=self.index_layers).return_poses()
```

Takeaway: a Runner does not have to use a JobStarter. The base class still
gives you score-file caching and DataFrame merging for free.

### 2. `ESMFold` — a single-binary subprocess runner

```python
def run(self, poses, prefix, jobstarter=None, options=None, overwrite=False, num_batches=None):
    work_dir, jobstarter = self.generic_run_setup(...)
    scorefile = f"{work_dir}/{prefix}_esmfold_scores.json"
    if (cached := self.check_for_existing_scorefile(scorefile, overwrite)) is not None:
        return RunnerOutput(poses, cached, prefix, self.index_layers).return_poses()

    # ensure fasta inputs
    if all(p.endswith(".pdb") for p in poses.poses_list()):
        poses.convert_pdb_to_fasta(prefix=prefix, update_poses=False, chain_sep=":")
        fastas = poses.df[f"{prefix}_fasta_location"].to_list()
    elif all(p.endswith((".fa", ".fasta", ".fas")) for p in poses.poses_list()):
        fastas = poses.poses_list()
    else:
        raise TypeError("ESMFold inputs must be all .pdb OR all .fa/.fasta")

    # batch and write cmds
    n_jobs = min(jobstarter.max_cores, len(fastas))
    batched = self.prep_fastas_for_prediction(fastas, fasta_dir=..., max_filenum=n_jobs)
    cmds = [f"{self.python} {auxiliary_script} {opts} {fa} {out_dir}" for fa in batched]
    if self.pre_cmd:
        cmds = [f"{self.pre_cmd}; " + c for c in cmds]

    jobstarter.start(cmds=cmds, jobname=prefix, wait=True, output_path=work_dir)

    scores = collect_esmfold_scores(out_dir)
    self.save_runner_scorefile(scores, scorefile)
    return RunnerOutput(poses, scores, prefix, self.index_layers).return_poses()
```

Takeaway: the runner's only real job is to (a) turn `poses` into a list of
commands, (b) call `jobstarter.start(...)`, and (c) parse the on-disk results
into a DataFrame with `description` + `location` + score columns.

### 3. `LigandMPNN` — adding `pose_opt_cols`

LigandMPNN takes structured per-pose options (fixed residues, hotspots, …).
The pattern:

```python
def run(self, poses, prefix, jobstarter=None, nseq=1, model_type=None, options=None,
        pose_options=None, fixed_res_col=None, design_res_col=None, pose_opt_cols=None,
        ...):
    pose_opt_cols = pose_opt_cols or {}
    if fixed_res_col is not None:
        pose_opt_cols["fixed_residues"] = fixed_res_col
    if design_res_col is not None:
        pose_opt_cols["redesigned_residues"] = design_res_col

    work_dir, jobstarter = self.generic_run_setup(...)
    ...

    # Convert pose_opt_cols (dict of cli_flag -> poses.df column) into per-pose option strings.
    pose_opt_cols_options = self.parse_pose_opt_cols(poses, pose_opt_cols, output_dir=work_dir)

    # Normalise pose_options (list or column name or None) to a list[str].
    pose_options = self.prep_pose_options(poses, pose_options)

    # Merge: pose_opt_cols_options wins on conflicts.
    pose_options = [
        options_flags_to_string(*parse_generic_options(po, popt, sep="--"), sep="--")
        for po, popt in zip(pose_options, pose_opt_cols_options)
    ]

    cmds = [self.write_cmd(pose, output_dir=work_dir, model=model_type, nseq=nseq,
                            options=options, pose_options=p_opts)
            for pose, p_opts in zip(poses.poses_list(), pose_options)]
    ...
```

Takeaway: `pose_opt_cols` is the right shape for *structured* per-pose
values — residue selections, fasta paths, contigs. The runner is responsible
for serialising each column's cell into the tool's CLI string. `pose_options`
is the right shape for *unstructured* per-pose CLI snippets.

## What `index_layers` should be

| Tool                                            | `index_layers` | Why |
|-------------------------------------------------|----------------|-----|
| ESMFold, ESM, ProtParam, BackboneRMSD, etc.     | `0`            | 1:1 input → output. Description unchanged. |
| RFdiffusion, LigandMPNN, ColabFold, AlphaFold3, ProteinGenerator, AttnPacker | `1` | One suffix added per output (sequence index, model number). |
| Boltz, RFdiffusion3 (with multiplexing)         | `2`            | Two suffixes: sample index *and* model index, or backbone *and* sequence. |

Set this once in `__init__`; runners that branch on multiplex behaviour set
it per-call in `run()`.
