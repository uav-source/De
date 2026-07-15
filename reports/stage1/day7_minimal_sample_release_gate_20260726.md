# Stage 1 Day 7 — Minimal Sample Release Gate

AUDIT_LABEL_DATE: 2026-07-26
EXECUTION_ENVIRONMENT_DATE: 2026-07-15
EXECUTION_ENVIRONMENT_TIMESTAMP: 2026-07-15T18:10:52+08:00

DAY6_GATE_VERIFIED: true

SELECTED_SOURCE_COUNT: 3
PLANNED_SAMPLE_COUNT: 3
DOWNLOADED_SOURCE_COUNT: 2
DOWNLOADED_SAMPLE_COUNT: 2
TOTAL_DOWNLOADED_BYTES: 5815083690

MINOR_ADAPTER_SAMPLE_COUNT: 1
OPEN_CONTROL_SAMPLE_COUNT: 1
UNDERGROUND_SAMPLE_COUNT: 0
UAV_SAMPLE_COUNT: 2

ARCHIVE_INTEGRITY_PASS_COUNT: 2
POINT_FIELD_VERIFIED_COUNT: 2
PER_POINT_TIME_VERIFIED_COUNT: 2
IMU_UNIT_VERIFIED_COUNT: 2
EXTRINSIC_VERIFIED_COUNT: 2
EXTRINSIC_DIRECTION_VERIFIED_COUNT: 2
GROUND_TRUTH_FORMAT_VERIFIED_COUNT: 2
SHORT_REPLAY_PASS_COUNT: 2

READY_MINOR_ADAPTER_COUNT: 1
READY_MAJOR_ADAPTER_COUNT: 1
READY_METADATA_ONLY_COUNT: 0
BLOCKED_SAMPLE_COUNT: 1
HOLD_LICENSE_COUNT: 1

SUBT_MRS_DOWNLOADED: false
SUBT_MRS_STATUS: HOLD_LICENSE

DAY8_ADAPTER_INPUT_SPEC_COMPLETE: true

DOWNLOAD_LIMIT_PASS: true
LARGE_DATASET_DOWNLOAD_PERFORMED: false
FASTLIO2_FORMAL_RUN_PERFORMED: false
ODI_REAL_DATA_RUN_PERFORMED: false
FORMAL_TRAJECTORY_EVALUATION_PERFORMED: false

SCIENTIFIC_CODE_MODIFIED: false
PATENT_DOC_MODIFIED: false
HISTORICAL_ARTIFACTS_MODIFIED: false
GIT_PUSH_PERFORMED: false

PYTEST_COMMAND: python3 -m pytest -q
PASSED: 187
FAILED: 0
SKIPPED: 0
WARNING_COUNT: 1
EXIT_CODE: 0

P0_ISSUE_COUNT: 0
P1_ISSUE_COUNT: 8
P2_ISSUE_COUNT: 3

DAY7_GATE: MINIMAL_SAMPLE_RELEASE_PASS_WITH_WARNINGS
## Gate basis

Day 6 was verified as `DATASET_FEASIBILITY_PASS_WITH_WARNINGS` with P0=0, no download, and no scientific-code modification before Day 7 began. All six required Day 6 dataset documents were present.

The three selected sources were MUN-FRL, NTU VIRAL, and Newer College Multi-Camera LiDAR-Inertial Extension. Two official sources were actually verified: MUN-FRL `Lighthouse_benchmarking_bag` supplies the MINOR/UAV sample, and NTU VIRAL `eee_03` supplies the open central-carpark control sample. Newer College `Stairs` remained `BLOCKED_DOWNLOAD` after an official-host quota response. Hilti Basement was not selected because its published minimum exceeds 4 GiB, and SubT-MRS remained `HOLD_LICENSE` and was not downloaded.

`TOTAL_DOWNLOADED_BYTES` is the retained network payload: two valid sample payloads totaling 5,808,136,874 bytes plus 6,946,816 bytes from an explicitly invalid, aborted NTU `rtp_03` partial. It excludes extracted duplicates and diagnostic range probes. MUN used 3,812,769,470 bytes; NTU used 2,002,314,220 bytes including the aborted partial. Both are below 4 GiB per source and the total is below 10 GiB. No full dataset was downloaded.

For the MUN ROS bag, “archive integrity” means successful indexed ROS bag opening and complete read probes. NTU additionally passed exact-size, official-MD5, SHA-256, ZIP CRC, member-list, and path-traversal checks. Both samples were inspected at head, middle, and tail, and both passed two short replay runs with identical per-topic counts, header ranges, and frame IDs and zero parse errors.

MUN is released as `READY_MINOR_ADAPTER`; NTU is released as `READY_MAJOR_ADAPTER` because its official timing regularization and linked-config corrections are mandatory. The release is input-contract readiness only. No FAST-LIO2 localization, ODI run, reference alignment, ATE/RPE evaluation, adapter implementation, threshold tuning, or patent update occurred.

## Warnings retained

The eight P1 and three P2 findings are listed without deletion in `docs/datasets/day7_sample_hold_and_issue_log_v1.md`. Principal warnings are the MUN record/header epoch split and position-only raw RTK, NTU timing jitter and linked-config defects resolved by archive YAML, Newer access quota, Hilti size, and SubT licensing. These warnings do not create a P0 ambiguity in either READY Day 8 input contract.

## Gate decision

All mandatory PASS conditions are met: two actual official sources; one open-control and one MINOR/UAV sample; actual point fields, point time/unit, IMU units, spatial extrinsics/direction, and GT formats; at least one READY adapter; SubT held; download limits respected; no formal algorithm/evaluation run; no scientific change; full pytest pass; and P0=0.

DAY7_GATE: MINIMAL_SAMPLE_RELEASE_PASS_WITH_WARNINGS
