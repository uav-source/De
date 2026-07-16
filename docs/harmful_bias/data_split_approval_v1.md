# Harmful-Bias Multihyp Data Split Approval V1

Approval ID: `HBMH_DATA_SPLIT_APPROVAL_V1`.

This approval freezes an engineering namespace allocation only. It does not approve scientific ground-truth labels, AUROC labels, or causal-truth labels. Every `DEGENERATE` and `CONTROL` role below remains:

```text
scientific_label_status=UNVERIFIED
eligible_as_ground_truth_label=false
eligible_for_auroc_label=false
```

## Fixed allocation

- Quick degenerate: `avia_quick_shack`
- Quick control: `avia_outdoor_run_100hz`
- Development degenerate: `avia_mainbuilding_100hz`, `avia_mainbuilding_10hz`, `avia_hku_mb`
- Development verified engineering control: `NTU_VIRAL__eee_03`
- Development auxiliary: `MUN_FRL__Lighthouse_benchmarking_bag`

The three Avia main-building sequences remain together in `avia_hku_mainbuilding_family`. The MUN sequence is an adapter-engineering auxiliary and is excluded from scientific control or degenerate counts.

## Deterministic Day 6 selection

The Day 6 sequence inventory has no explicit proposal-rank column. The approved fallback is therefore `dataset_id` ascending, then canonical `sequence_id` ascending. The source and column resolution is frozen in `manifests/harmful_bias/data_split_source_resolution.json`.

- Development extra control: `HELIPR__Roundabout01`
- Holdout degenerate: `HELIPR__Bridge02`
- Holdout control: `M2DGR__room_01`
- Future degenerate: `HELIPR__Town02`, `HILTI_2021__Basement`, `HILTI_2021__Basement_3`, `M2DGR__hall_02`
- Future control: `M2DGR__street_02`, `MULRAN__DCC01`, `MULRAN__KAIST01`, `MUN_FRL__quarry1`

Future Test contains eight complete sequence records from five sources, with no source contributing more than two entries.

## Holds and exclusions

- Every SubT-MRS row remains `HOLD_LICENSE` and selected namespace `NONE`.
- Newer College `Stairs` remains `BLOCKED_DOWNLOAD` and selected namespace `NONE`.
- Day 13 Evaluation is synthetic and remains outside all four namespaces.
- Holdout and Future Test both retain `run_authorized=false`.
- Future Test retains `run_count=0`.

No dataset was downloaded and no Quick, Development, Holdout, or Future run was performed while applying this approval.
