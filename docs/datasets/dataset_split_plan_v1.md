# Dataset Sequence-Level Split Plan v1

- Audit label date: 2026-07-25
- Execution date: 2026-07-15
- Status: proposal only. No Reserved Test is locked in Day 6.

## Non-negotiable rules

1. Split only by complete sequence; never randomly split frames.
2. Treat same-place repeats and near-duplicate routes as one `location_group`.
3. A location group used for adapter debugging, threshold selection or format repair cannot later become Reserved Test.
4. Development is for decoding, synchronization, frame/extrinsic verification, adapter code and threshold exploration.
5. Validation is used once per declared candidate setting before method/threshold freeze; it must not become iterative tuning data.
6. Reserved Test is selected and sealed only after code, method and thresholds are frozen. Day 6 selects no final Reserved Test.
7. Open Control is evaluation-only and independent from difficult-scene threshold tuning.
8. A sequence without full GT coverage cannot produce the primary ATE result. It may support sparse checkpoint error or qualitative detection analysis if labeled.
9. Failed intervals, missing topics, time jumps and dropped frames are reported; they are never silently removed to improve a metric.

## Proposed grouping

### Development groups

- `mun_dji_lighthouse`: MUN-FRL `lighthouse`; first format and replay probe.
- `subt_hawkins`: SubT-MRS `Long_Corridor` and `Multi_Floor`, conditional on license clearance.
- `hilti_basement`: Hilti `Basement`, `Basement_3`, `Basement_4`; adapter plus sparse-GT inspection.
- `ncd_multicam_college`: Newer College Extension `Stairs`, `Cloister`, `Park`; all remain together.
- `ntu_tnp`: NTU VIRAL `tnp_01`, `tnp_02`, `tnp_03`; all remain together because they repeat the same facility.
- `m2dgr_room` and `m2dgr_roomdark`: adapter/GT sanity checks; do not promote a used sequence to Test.

### Validation groups

- `mun_dji_quarry`: MUN-FRL `quarry1`/`quarry2`; keep both together if either is used for setting selection.
- `tiers_indoor_corridor`: TIERS `Indoor09`/`Indoor10`; validation only, with SLAM+ICP-reference caveat.
- `m2dgr_hall`: M2DGR hall sequences as one group.
- `helipr_town`: all selected Town repeats as one group after the major adapter is stable.
- `mulran_riverside`: Riverside01/02/03 as one long-term group.

### Open Control groups

- `ncd_multicam_maths`: all Maths Easy/Medium/Hard sequences remain evaluation-only; `Maths-Easy` is the normal-control headline.
- `ncd_original_college`: short/long original sequences remain evaluation-only if used as control.
- `ntu_eee`: EEE carpark sequences remain independent from TNP indoor tuning.
- `m2dgr_street`: choose a complete daytime street group after the adapter is fixed.
- `mulran_kaist` or `mulran_dcc`: choose one entire urban group; do not tune on it.
- `tiers_road`: `Road3`, not Indoor09/10, is the independent TIERS control.

### Future Reserved Test candidates—not locked

- SubT-MRS `BlockLiDAR`/Mill19 group, if its modality and full GT are confirmed.
- Hilti construction-site group, for sparse checkpoint evaluation only unless a full reference is released.
- MUN-FRL one Bell412 group, after DJI sequences work and the selected GT package is complete.
- A Newer College location family not previously used for adaptation or threshold selection.

## Metric eligibility

| Reference coverage | Allowed primary use | Disallowed claim |
|---|---|---|
| Full time-aligned 6DoF | ATE/RPE, translation/rotation drift, detection alignment | None beyond stated reference accuracy/provenance |
| Full position only | Position ATE/RMSE, detection alignment | Rotation error against GT |
| Sparse 3DoF checkpoints | Checkpoint translation error | Full-trajectory ATE/RPE |
| Generated SLAM+ICP reference | ATE/RPE with provenance caveat | Independent external-ground-truth claim |
| No complete GT | Qualitative detection/failure case | Primary trajectory-accuracy result |

The detailed proposed sequence rows and location groups are in `dataset_sequence_inventory_v1.csv`.
