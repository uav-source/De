# Harmful-Bias Multihyp Day 1 Data Split Decisions — Resolved

## Status

The prior Day 1 decision block is resolved by approval:

```text
approval_id=HBMH_DATA_SPLIT_APPROVAL_V1
DATA_SPLIT_APPROVAL_APPLIED=true
DATA_NAMESPACE_FROZEN=true
```

The approval is limited to engineering namespace allocation. It does not turn human-assigned `DEGENERATE` or `CONTROL` roles into scientific ground truth, AUROC labels, or causal truth.

## Resolution

The fixed Avia, NTU VIRAL, and MUN-FRL assignments were applied exactly as authorized. Remaining Development, Holdout, and Future entries were selected from the existing Day 6 sequence-level inventory.

Because the Day 6 CSV has no explicit proposal-rank column, the approved deterministic fallback was:

1. `dataset_id` ascending;
2. canonical `sequence_id` ascending.

The complete candidate-by-candidate disposition and rejection reasons are in:

```text
manifests/harmful_bias/data_namespace_selection_audit.csv
```

## Preserved restrictions

- SubT-MRS remains `HOLD_LICENSE` and unselected.
- Newer College `Stairs` remains `BLOCKED_DOWNLOAD` and unselected.
- Day 13 Evaluation remains outside every namespace.
- Holdout-Dev has `run_authorized=false`.
- Future Test has `run_authorized=false` and `run_count=0`.
- No dataset download or algorithm run was performed.

No further Day 1 split decision is pending. Changes to this namespace require a new explicit approval and a new versioned artifact.
