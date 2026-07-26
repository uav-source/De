# Day 6 Experiment A Input and Map Stage Hash Report

Result identity: `INTERNAL_ENGINEERING_DIVERGENCE_STAGE_DIAGNOSTICS_ONLY`.

1. Both restricted replays complete: `True`.
2. Branch reproduced in the diagnostic window: `True`.
3. First divergence scan: `135`.
4. Raw LiDAR identity: `MATCHED_BY_CANONICAL_CHECKSUM`.
5. IMU bundle identity: `MATCHED_BY_CANONICAL_CHECKSUM`.
6. Undistorted cloud identity: `MATCHED_BY_CANONICAL_CHECKSUM`.
7. Prior state/covariance identity: `MATCHED_BY_CANONICAL_CHECKSUM` / `MATCHED_BY_CANONICAL_CHECKSUM`.
8. Map content before measurement: `MATCHED_BY_CANONICAL_CHECKSUM`.
9. Map traversal before measurement: `DIVERGED`.
10. Correspondence/J/h does not separate anywhere in scan 135–160; aggregate status is `MATCHED_BY_CANONICAL_CHECKSUM`.
11. Post-update state/covariance does not separate anywhere in scan 135–160; aggregate status is `MATCHED_BY_CANONICAL_CHECKSUM`.
12. Insertion batch identity: `MATCHED_BY_CANONICAL_CHECKSUM`.
13. Map content after insertion: `DIVERGED`.
14. Map traversal after insertion: `DIVERGED`.
15. Classification: `MAP_INSERTION_STAGE_DIVERGED`.
16. Checksum limitation: equal values mean only `MATCHED_BY_CANONICAL_CHECKSUM`; finite FNV-1a checksums may collide.
17. The evidence does not identify a particular point; full payloads, maps, neighbors, planes, and accepted-index arrays were not exported.
18. OpenMP data race proven: `false`.
19. ikd-tree root cause proven: `false`.
20. Day 7 recommended: `False`; scope: `NONE`.
21. Day 7 remains unauthorized because this bounded engineering checksum result requires a separate GPT audit.

`EXPERIMENT_A_EXECUTION_PASS=true`

`EXPERIMENT_A_STAGE_LOCALIZATION_PASS=true`

`EXPERIMENT_A_PASS=true`

Fixed state remains `STAGE2_GATE=FAIL`, `TRANSITION=PIVOT`,
`CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`, and
`HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY6_EXPERIMENT_A_INPUT_MAP_HASHES`.
The production detector, ODI, weak-direction logic, GT, Development, Holdout,
and Future Test were not run.

FAST test-link remediation disclosure:

- `FAST_PRODUCTION_BUILD_COUNT=1`
- `FAST_PRODUCTION_BUILD_RERUN_AFTER_TEST_FIX=false`
- `FAST_NEW_TEST_TARGET_RELINKED=true`
- `FAST_TEST_GATE_RERUN=true`
- `GTEST_MAIN_REMEDIATION_ONLY=true`
- Degen targeted tests: `27 passed`
- Degen full tests: `1084 passed, 1 skipped`
