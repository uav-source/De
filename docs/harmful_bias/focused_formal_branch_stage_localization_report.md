# Day 6 Focused Formal Branch Stage Localization Report

## Outcome

The experiment stopped fail-closed during the first authorized run. The frozen
FAST-LIO2 binary reads the requested scan parameters, but its
`ExperimentAStageHashAudit::configure` implementation rejects any window with
more than 26 records. The fixed inclusive window 155–205 requests 51 records.
FAST-LIO2 therefore exited with:

`Invalid Day 6 Experiment A stage-hash configuration.`

This is exactly the task's stop condition for an existing FAST build that
cannot cover the authorized window through parameters. FAST source, binary,
snapshot implementation, thread settings, and estimator behavior were not
modified.

## Execution accounting

Two candidate run locks were rejected before ROS started: the first exposed an
authorization-field routing error, and the second exposed missing frozen
transport source-lock fields. Both failures consumed zero replay attempts.
Their identities and rejection evidence are retained.

The accepted lock passed a transport-input and source-lock dry run. Run 1 then
started a fresh roscore on port 20211, roslaunch, the frozen FAST-LIO2 binary,
and a paused rosbag process. FAST-LIO2 rejected the 51-record window during
configuration before the bag was unpaused. Consequently:

- LiDAR callbacks: 0
- IMU callbacks: 0
- observation records: 0
- stage records: 0
- coherent snapshots: 0
- wrapper exit code: 1
- raw runner exit code: 30
- failure classification: `RUNTIME_PRODUCT_MISSING`

No ROS processes remained afterward. Per the completeness Gate, runs 2–4 were
not started. A fifth run was not started.

## Gate

`FOCUSED_FORMAL_BRANCH_LOCALIZATION_EXECUTION_PASS=false`

`FOUR_REPLAY_RUNS_COMPLETE_PASS=false`

`FORMAL_BRANCH_REPRODUCED=false`

`FORMAL_BRANCH_STAGE_LOCALIZED=false`

`EXPERIMENT_A_PASS=false`

`DAY7_RECOMMENDED=false`

`DAY7_AUTHORIZED=false`

The `FORMAL_BRANCH_REPRODUCED=false` value is an execution-gate value, not
evidence that four valid replays lacked a branch. The correct status is
`EXECUTION_BLOCKED_BEFORE_OBSERVATION_CAPTURE`.

No pairwise semantic or focused-stage comparisons, previous-scan checks,
trajectory clusters, or result plots were produced because there was no valid
observation matrix. Creating any of them would fabricate evidence.

## Fixed scientific boundary

- `STAGE2_GATE=FAIL`
- `TRANSITION=PIVOT`
- `STAGE3_START_AUTHORIZED=false`
- `FAST_LIO2_INTEGRATION_AUTHORIZED=false`
- `CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`
- `HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY6_FOCUSED_FORMAL_BRANCH_STAGE_LOCALIZATION`

The detector was not run, ODI and weak directions were not computed, GT was
not consumed, and detector effectiveness was not evaluated. Day 7 still
requires a new explicit authorization after review; this result cannot enter
FAST robust-update integration automatically.
