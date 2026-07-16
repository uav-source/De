# Harmful-Bias Multihyp Day 1 Remediation V2 Report

## Result

Remediation V2 passed. The missing trusted archive was recovered from the desktop trash, verified against the fixed SHA-256, restored to its original HOME path, and used to restore all eight historical HOME evidence files.

The Pivot tag and six-week spike branch both point to the frozen Day 14 commit:

```text
531e25de917ec527645d2e6633592145826c81d6
```

## Baseline recovery

- V3 archive SHA verification: pass.
- V3 gzip verification: pass.
- V3 internal hash failures: 0.
- required HOME files: 8.
- restored: 8.
- already matched: 0.
- conflicts: 0.
- pytest before restoration: `576 passed, 14 failed, 1 warning in 39.05s`.
- first pytest after restoration: `590 passed, 1 warning in 51.96s`.

## Data source resolution

Day 6 and Day 7 evidence was resolved from the existing repository only. No network or download operation occurred.

The sequence inventory has no rank column, so sorting fell back to `dataset_id` and canonical sequence ID. Column mapping, source paths, source SHA-256 values, and canonicalization are recorded in `data_split_source_resolution.json`.

```text
ambiguity_count=0
invented_sequence_id_count=0
```

## Namespace result

### Quick

- degenerate: `avia_quick_shack`
- control: `avia_outdoor_run_100hz`

### Development

- degenerate: `avia_mainbuilding_100hz`
- degenerate: `avia_mainbuilding_10hz`
- degenerate: `avia_hku_mb`
- control: `NTU_VIRAL__eee_03`
- control: `HELIPR__Roundabout01`
- auxiliary: `MUN_FRL__Lighthouse_benchmarking_bag`

### Holdout-Dev

- degenerate: `HELIPR__Bridge02`
- control: `M2DGR__room_01`

### Future Test

- degenerate: `HELIPR__Town02`
- degenerate: `HILTI_2021__Basement`
- degenerate: `HILTI_2021__Basement_3`
- degenerate: `M2DGR__hall_02`
- control: `M2DGR__street_02`
- control: `MULRAN__DCC01`
- control: `MULRAN__KAIST01`
- control: `MUN_FRL__quarry1`

Future Test has five sources and at most two sequences per source.

## Validation

```text
duplicate_sequence_count=0
cross_namespace_overlap_count=0
cross_location_family_overlap_count=0
day13_overlap_count=0
subt_selected_count=0
stairs_selected_count=0
future_run_count=0
```

All human roles remain scientifically unverified and cannot be used as AUROC ground-truth labels.

Day 1 close-out hardening explicitly seals Holdout-Dev and Future Test and records all required provenance, hash, role, availability, and authorization fields inside each of the 18 sequence entries.

## Scope

Only `docs/harmful_bias/` and `manifests/harmful_bias/` were changed. No source, script, test, configuration, README, or FAST-LIO2 source file changed. No build, rosbag, data download, observation tap, scientific experiment, commit, or push occurred.

Day 2 is authorized but was not entered. Stage 2 remains `FAIL`, transition remains `PIVOT`, Stage 3 and FAST-LIO2 integration remain unauthorized, and formal Degen-LIO remains incomplete.
