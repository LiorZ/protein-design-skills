# Filtering and Scoring

ProtFlow filters and aggregates entirely inside the `Poses` object. Every
method mutates `poses.df` in place and (where it makes sense) returns the
Poses for chaining.

## `filter_poses_by_value`

```python
poses.filter_poses_by_value(
    score_col,         # column name
    value,             # scalar threshold
    operator,          # one of: "<", "<=", ">", ">=", "==", "!="
    prefix=None,       # if set, dump a filter-audit scorefile under work_dir/filter/<prefix>_*
    plot=False,        # density plot of before vs after
    plot_cols=None,    # extra columns to include on the plot
    overwrite=True,
    storage_format=None,
    fail_on_empty=True,
) -> Poses
```

Example:

```python
poses.filter_poses_by_value(score_col="esm_plddt", value=0.7, operator=">=")
poses.filter_poses_by_value(score_col="rmsd_rmsd", value=2.0, operator="<=",
                             prefix="post_sc_filter", plot=True)
```

Set `fail_on_empty=False` if it's OK to end up with zero rows after filtering
— useful in pipelines where some branches genuinely have no passing designs.

## `filter_poses_by_rank`

```python
poses.filter_poses_by_rank(
    n,                  # int → top-N; 0 < float < 1 → top fraction
    score_col,
    group_col=None,     # rank within each group (e.g. per backbone)
    remove_layers=None, # group implicitly by stripping N suffixes from poses_description
    layer_col="poses_description",
    sep="_",
    ascending=True,     # True ⇒ keep smallest (RMSD); False ⇒ keep largest (pLDDT)
    prefix=None,        # filter-audit prefix
    plot=False,
    plot_cols=None,
    overwrite=True,
    storage_format=None,
) -> Poses
```

Examples:

```python
# Keep the top 50 by predicted confidence
poses.filter_poses_by_rank(n=50, score_col="esm_plddt", ascending=False)

# Keep the best-1 sequence per backbone (assuming MPNN added one '_N' suffix per sequence)
poses.filter_poses_by_rank(n=1, score_col="esm_plddt", ascending=False,
                            remove_layers=1)

# Keep the top 10% of all designs
poses.filter_poses_by_rank(n=0.1, score_col="composite", ascending=True)
```

`remove_layers` is the cleanest way to "keep the best child per parent": it
strips that many `_<idx>` suffixes from `poses_description` to compute a
group key, then keeps the top-N within each group.

## `calculate_composite_score`

```python
poses.calculate_composite_score(
    name,                # name of the new column
    scoreterms,          # list of column names
    weights,             # list of floats (same length)
    plot=False,
    scale_output=False,  # min-max scale the composite to [0, 1]
) -> Poses
```

Mechanics:

1. Each `scoreterm` is z-normalised across the current poses
   (`normalize_series`, with optional scaling).
2. The normalised series are linearly combined with the given weights.
3. The result lands in `poses.df[name]`.

By convention, **lower is better** for each term *after* normalisation —
weights are typically positive for "lower is better" metrics (RMSD, PAE)
and negative for "higher is better" (pLDDT, ipTM). Composite values are
unitless and only meaningful as a ranking.

Example:

```python
poses.calculate_composite_score(
    name="rank",
    scoreterms=["rmsd_rmsd", "esm_plddt", "esm_ptm"],
    weights=[1.0, -1.0, -1.0],            # minimise RMSD; maximise pLDDT & pTM
    plot=True,
    scale_output=False,
)
poses.filter_poses_by_rank(n=50, score_col="rank", ascending=True)
```

## Aggregating across groups

For "for each backbone, compute the mean pLDDT across its 8 sequences":

```python
poses.calculate_mean_score(
    name="mean_plddt_per_backbone",
    score_col="esm_plddt",
    remove_layers=1,    # group by stripping one '_N' from poses_description
)
```

The mean / median / std / max / min variants all share the same signature:

```python
.calculate_<agg>_score(
    name,
    score_col,
    skipna=False,
    remove_layers=None,
    sep="_",
)
```

`remove_layers=N` groups by the first `len(poses_description) - N` chunks of
the `_`-split description; without it, every row is its own group (use a
plain pandas groupby if you need more control).

## Auditing filters

When you pass `prefix=` to a filter, ProtFlow writes:

```
work_dir/filter/<prefix>_before_filter.<storage_format>   # the DataFrame as it stood
work_dir/filter/<prefix>_after_filter.<storage_format>    # the surviving subset
work_dir/filter/<prefix>_filter_args.json                  # the filter parameters
```

This is the audit trail you want when you have to defend the campaign's
final list of designs three months later.

If `plot=True`, the `plots/` directory gets a density plot of the column
(or scatter when `plot_cols` is set).

## Module-level helpers

For ad-hoc analysis that doesn't deserve a `Poses` object:

```python
from protflow.poses import (
    filter_dataframe_by_value,
    filter_dataframe_by_rank,
    combine_dataframe_score_columns,
    normalize_series,
    scale_series,
)

df_filtered = filter_dataframe_by_rank(df, col="plddt", n=50, ascending=False)
df_filtered = filter_dataframe_by_value(df, col="rmsd", value=2.0, operator="<=")
composite   = combine_dataframe_score_columns(
    df, scoreterms=["rmsd", "plddt"], weights=[1.0, -1.0], scale=False
)
```

These are pure functions over `pd.DataFrame` / `pd.Series` and are
extensively used inside the Poses methods.
