# Day 6 Focused Formal Branch Stage Localization Contract

## Purpose and scientific boundary

This bounded internal-engineering experiment executes exactly four new
`avia_quick_shack` replays and localizes any reproduced formal branch with
compact stage evidence from the fixed inclusive scan window 155–205. The
experiment does not evaluate harmful-bias detectability, detector
effectiveness, ODI, AIS, eigengap, weak directions, ground truth, or a robust
FAST-LIO2 update.

The result identity is
`INTERNAL_ENGINEERING_BRANCH_STAGE_LOCALIZATION_ONLY`. It is not scientific
causal proof, data-race proof, ikd-tree root-cause proof, a Day 7 result, or a
Stage 3 result.

## Frozen inputs and execution

- Authorization audit SHA-256:
  `f092a4910667eded36a04d966128e2e9a11e7226711297a78dca11cf50e54fa3`.
- Quick Shack clip SHA-256:
  `272325265978787c838e010b1f0da963a15fb4b08ff8730fc3dd9901e32a0e20`.
- Diagnostic window: scans 155–205 inclusive.
- Expected per run: 491 LiDAR callbacks, 9953 IMU callbacks, 490 runtime
  scans, 487 observations, 51 StageHashRecordV2 records, and 102 coherent
  snapshots (51 before and 51 after).
- Runs are sequential, use four distinct ROS master ports, and stop at four.
  A fifth replay is neither recommended nor authorized.

FAST-LIO2 source, binary, synchronized snapshot implementation, formal
estimator behavior, threading, CPU affinity, and clip are locked. The runtime
window is selected only through the existing
`/harmful_bias/experiment_a_scan_start` and
`/harmful_bias/experiment_a_scan_end` parameters. FAST-LIO2 is not rebuilt or
tested in this task.

## Formal branch and stage evidence

Identity-only, file, process, logging, timing, rebuild-generation, or
traversal-only differences are not formal branches. Formal branch fields are
prior state or covariance, logical map content, accepted-index or formal
correspondence checksums, formal Jacobian/innovation/residual values,
post-update state or covariance, insertion batch, and logical map content
after insertion.

Each of the six run pairs is compared over all 487 semantic observations and
all 51 focused stage records. A branch inside the window is localized only
when the aligned stage record is present, both map snapshots are coherent,
cross-scan continuity passes, and the preceding scan identity is checked.
Stage classifications are limited to:

- `INPUT_STAGE_DIVERGED`
- `UNDISTORTION_OR_IMU_PROCESSING_STAGE_DIVERGED`
- `MAP_STATE_ALREADY_DIVERGED`
- `IKDTREE_TRAVERSAL_ORDER_ASSOCIATED_CORRESPONDENCE_DIVERGENCE`
- `CORRESPONDENCE_CONSTRUCTION_DIVERGED_WITH_MATCHED_INPUT_AND_MAP_CONTENT`
- `FILTER_UPDATE_STAGE_DIVERGED`
- `MAP_INSERTION_STAGE_DIVERGED`
- `NO_FORMAL_DIVERGENCE`
- `EVIDENCE_GAP`

Traversal-order association is evidence of association only and is never
reported as root-cause proof.

## Fail-closed gates

Any run-integrity failure stops later unstarted replays and prevents the
four-run Gate from passing. Missing or incoherent focused evidence, a
full-stream branch outside scans 155–205, a mismatch between full-stream and
focused first-divergence scans, or an unexplained prior-scan difference keeps
`FORMAL_BRANCH_STAGE_LOCALIZED=false`.

Day 7 may be recommended only for a reproduced, completely localized mode
allowed by the task decision table. Recommendation never authorizes execution:

`DAY7_AUTHORIZED=false`

The fixed research boundary remains:

- `STAGE2_GATE=FAIL`
- `TRANSITION=PIVOT`
- `STAGE3_START_AUTHORIZED=false`
- `STAGE4_START_AUTHORIZED=false`
- `FAST_LIO2_INTEGRATION_AUTHORIZED=false`
- `CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`
- `HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY6_FOCUSED_FORMAL_BRANCH_STAGE_LOCALIZATION`
