# Experiment A Map Snapshot Coherence Report

Result identity:
`INTERNAL_ENGINEERING_MAP_SNAPSHOT_DIAGNOSTICS_ONLY`.

1. The prior 596-point value was produced by an unlocked recursive diagnostic
   traversal that could overlap background flatten, subtree replacement,
   logger replay, and old-node disposal. It was not a coherent observation of
   the logical map, so the 596 to 1575 interpretation and the old
   map-insertion classification are revoked. This does not prove which
   concurrent operation caused the partial traversal.
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
18. Prior state, prior covariance, post-update state, and post-update
    covariance identity: MATCHED_BY_CANONICAL_CHECKSUM.
19. Insertion-batch identity: MATCHED_BY_CANONICAL_CHECKSUM.
20. Coherent map-content-after identity:
    MATCHED_BY_CANONICAL_CHECKSUM. Coherent map-traversal-after identity:
    DIVERGED.
21. The original scan-147 measurement/correspondence branch was not
    reproduced. A distinct storage-order-only traversal difference was
    observed at scan 135; logical map content and all formal downstream
    stages remained matched.
22. First divergence: scan 135,
    stage map_traversal_after.
23. Stage classification: `MAP_STORAGE_ORDER_DIFFERED_WITH_MATCHED_CONTENT`.
24. Checksums are compact engineering identity evidence with a theoretical
    collision limitation.
25. This task does not prove a data race.
26. This task does not prove ikd-tree caused the original Day 6 branch.
27. Day 7 recommended:
    false;
    scope `NONE`, because the traversal difference did not propagate into
    correspondence.
28. Day 7 remains unauthorized pending GPT audit. No third replay was added.

The snapshot lock can slightly perturb background thread timing. Content digest
is order-independent; traversal digest is order-sensitive. Detector, ODI, weak
direction, GT, development, holdout, and future-test paths were not run.

Both real replays completed ROS, rosbag, FAST, endpoint callback, drain, and
normal shutdown work. Their wrappers then exited 1 during post-run
materialization because the inherited code read `ros_master_port` from FAST's
`run_summary.json` instead of the transport `run_metadata.json`. No replay was
repeated. The raw products were preserved, and snapshot evidence was
materialized offline from the frozen V2 stage records with the ports fixed by
the immutable runtime lock.

The first offline classifier mapped `map_traversal_after` to map insertion,
contrary to the task's explicit matched-content/traversal-difference rule.
Only that offline mapping and its regression test were corrected. Runtime
source, FAST source, production binary, parameters, observations, stage
records, and snapshots were unchanged; runtime-lock to analysis-lock lineage
is included in the audit.

Final validation: Degen targeted tests 38 passed; Degen full tests 1102 passed,
1 skipped; FAST tests 256 passed with zero errors or failures. The FAST
production build was not rerun after the test-fixture-only heap-allocation
correction. The production binary remained
`3dff4043d7450c0454c1cecedc0baf092e2cc8c47fecab10fd2fe014d0b00250`.

`EXPERIMENT_A_MAP_SNAPSHOT_REMEDIATION_EXECUTION_PASS=true`

`EXPERIMENT_A_STAGE_LOCALIZATION_PASS=true`

`EXPERIMENT_A_PASS=true`

`DAY7_AUTHORIZED=false`

`STAGE2_GATE=FAIL`

`TRANSITION=PIVOT`
