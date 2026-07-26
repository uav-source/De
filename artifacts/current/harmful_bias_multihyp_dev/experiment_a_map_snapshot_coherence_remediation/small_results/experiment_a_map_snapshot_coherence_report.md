# Experiment A Map Snapshot Coherence Report

Result identity:
`INTERNAL_ENGINEERING_MAP_SNAPSHOT_DIAGNOSTICS_ONLY`.

1. The prior 596 to 1575 anomaly came from an unlocked recursive read that
   could overlap background flatten, subtree replacement, logger replay, and
   old-node disposal. The 596-point observation is revoked.
2. The former traversal had no global reader admission or lifetime guard.
3. The current snapshot uses `rebuild_ptr_mutex_lock` then
   `working_flag_mutex`, matching the formal rebuild lock order.
4. A new read-only `KD_TREE::Snapshot_Valid_Points_Coherent` API was added.
5. The lock order matches the audited formal rebuild order.
6. Snapshot code copies points and metadata only; formal state, covariance,
   search, Add/Delete result, rebuild trigger, and OpenMP behavior are
   unchanged.
7. Coherent snapshots: 104/104.
8. Every successful validnum equals its copied point count:
   true.
9. Rebuild generation is stable within each successful snapshot.
10. Logical mutation counter is stable within each successful snapshot.
11. Cross-scan violations, including count increase without Add:
    0.
12. Raw LiDAR identity: MATCHED_BY_CANONICAL_CHECKSUM.
13. IMU bundle identity: MATCHED_BY_CANONICAL_CHECKSUM.
14. Undistorted-cloud identity: MATCHED_BY_CANONICAL_CHECKSUM.
15. Coherent map-content-before identity:
    MATCHED_BY_CANONICAL_CHECKSUM.
16. Coherent map-traversal-before identity:
    DIVERGED.
17. Correspondence identity: MATCHED_BY_CANONICAL_CHECKSUM.
18. Post-update state identity: MATCHED_BY_CANONICAL_CHECKSUM.
19. Insertion-batch identity: MATCHED_BY_CANONICAL_CHECKSUM.
20. Coherent map-content-after identity:
    MATCHED_BY_CANONICAL_CHECKSUM.
21. Formal branch reproduced:
    true.
22. First divergence: scan 135,
    stage map_traversal_after.
23. Stage classification: `MAP_STORAGE_ORDER_DIFFERED_WITH_MATCHED_CONTENT`.
24. Checksums are compact engineering identity evidence with a theoretical
    collision limitation.
25. This task does not prove a data race.
26. This task does not prove ikd-tree caused the original Day 6 branch.
27. Day 7 recommended:
    false;
    scope `NONE`.
28. Day 7 remains unauthorized pending GPT audit. No third replay was added.

The snapshot lock can slightly perturb background thread timing. Content digest
is order-independent; traversal digest is order-sensitive. Detector, ODI, weak
direction, GT, development, holdout, and future-test paths were not run.

`EXPERIMENT_A_MAP_SNAPSHOT_REMEDIATION_EXECUTION_PASS=true`

`EXPERIMENT_A_STAGE_LOCALIZATION_PASS=true`

`EXPERIMENT_A_PASS=true`

`DAY7_AUTHORIZED=false`

`STAGE2_GATE=FAIL`

`TRANSITION=PIVOT`
