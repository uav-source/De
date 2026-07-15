# Stage 1 Day 6 Public Dataset Feasibility Gate

AUDIT_LABEL_DATE: 2026-07-25
EXECUTION_ENVIRONMENT_DATE: 2026-07-15
EXECUTION_ENVIRONMENT_TIMESTAMP: 2026-07-15T17:54:01+08:00

CANDIDATE_DATASET_COUNT: 10
OFFICIAL_SOURCE_VERIFIED_COUNT: 10
DEEP_AUDIT_DATASET_COUNT: 10

VERIFIED_USABLE_COUNT: 1
USABLE_WITH_ADAPTER_COUNT: 8
LIMITED_USE_COUNT: 1
REJECTED_COUNT: 0

TUNNEL_OR_UNDERGROUND_SOURCE_COUNT: 2
OPEN_CONTROL_SOURCE_COUNT: 10
UAV_GENERALIZATION_CANDIDATE_COUNT: 3
LIDAR_IMU_SOURCE_COUNT: 10
GROUND_TRUTH_SOURCE_COUNT: 10
LICENSE_VERIFIED_COUNT: 9

PRIMARY_DEGENERATE_SOURCE_IDENTIFIED: true
PRIMARY_DEGENERATE_SOURCE: SubT-MRS
SECONDARY_DEGENERATE_SOURCE_IDENTIFIED: true
SECONDARY_DEGENERATE_SOURCE: Hilti SLAM Challenge Dataset 2021
OPEN_CONTROL_SOURCE_IDENTIFIED: true
OPEN_CONTROL_SOURCE: Newer College Multi-Camera LiDAR-Inertial Extension

FASTLIO2_DIRECT_COUNT: 0
FASTLIO2_MINOR_ADAPTER_COUNT: 2
FASTLIO2_MAJOR_ADAPTER_COUNT: 8

SEQUENCE_LEVEL_SPLIT_COMPLETE: true
DOWNLOAD_PERFORMED: false
FORMAL_EXPERIMENTS_RERUN: false

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
P1_ISSUE_COUNT: 4
P2_ISSUE_COUNT: 3

DAY6_GATE: DATASET_FEASIBILITY_PASS_WITH_WARNINGS

## Gate rationale

Ten named candidates were checked against 32 records from official dataset sites, official repositories, formal dataset papers, or official documentation. All ten received a field-level and sequence-level feasibility audit. Nine have explicit license/use terms; SubT-MRS remains `LIMITED_USE` because no explicit dataset license was found in the audited official pages. The status distribution is one `VERIFIED_USABLE`, eight `USABLE_WITH_ADAPTER`, one `LIMITED_USE`, and no manufactured rejection.

The two tunnel/underground sources are SubT-MRS and Hilti basement sequences. All ten sources contain at least one candidate open/control scene in the source matrix; the eight stronger control candidates named in the matrix narrative exclude SubT-MRS and Hilti from the headline control set. The three aerial-platform candidates are SubT-MRS, NTU VIRAL, and MUN-FRL. MUN-FRL and NTU VIRAL are the preferred UAV-generalization sources; the SubT-MRS aerial subset is conditional.

FAST-LIO2 compatibility was checked on all 17 required dimensions for every candidate. No source was labelled `DIRECT` merely because it provides a ROS bag. MUN-FRL and NTU VIRAL are `MINOR_ADAPTER`; the other eight are `MAJOR_ADAPTER`. These are documentation-based estimates, not successful replay claims.

The proposed split is by complete sequence and keeps same-location families together. No Reserved Test is locked at Day 6. No data was downloaded or converted, FAST-LIO2 was not run, and no formal experiment was rerun. Scientific code, tests, configurations, historical artifacts, README, and the patent document were not modified. Full pytest passed.

## Warnings retained

### P1

1. SubT-MRS has the strongest tunnel/underground relevance, but its audited official pages do not state an explicit dataset license. It remains on hold until written use terms are clarified.
2. Exact point fields, within-scan time units, IMU units, and LiDAR–IMU transform direction remain sample-level checks for several candidates. No formal FAST-LIO2 run is authorized until the selected sample passes the compatibility release condition.
3. Most Hilti 2021 sequences provide sparse stationary 3DoF total-station control rather than continuous full-trajectory 6DoF truth. Their accuracy evidence must use checkpoint metrics, not blanket ATE/RPE.
4. Large-file hosts, request forms, and access stability vary by source. Availability must be rechecked immediately before any later minimal download.

### P2

1. Ground-truth provenance and coverage vary: NTU VIRAL lacks independent orientation GT, TIERS indoor reference is SLAM-assisted ICP, and some MUN-FRL 6DoF references may include aided estimation. Metric wording must retain those boundaries.
2. The sequence plan is a proposal only. Reserved Test remains intentionally unlocked until adapter, method, and thresholds are frozen.
3. Related locations and repeated collections must remain grouped when the split is finalized; no frame-random split or same-site leakage is permitted.

The complete evidence trail, scores, sequence inventory, split proposal, recommendation, hold log, and compatibility findings are in `docs/datasets/`.
