# Day 8 Focused Traversal Witness Remediation Report

## Outcome

The focused remediation did not pass. The first real replay completed its ROS
and rosbag data flow, but the frozen offline wrapper exited during post-replay
materialization. Runs 2--4 were not started, as required by the per-run
stop-on-failure gate.

## Pre-run remediation

- Source scan 157 had no detailed tokens because the prior token window was
  160--163.
- Missing/window-excluded token evidence now has an explicit NOT_CAPTURED
  status and cannot establish equal traversal traces.
- The run2 source 47/46 discrepancy was representative-level versus full
  logical-voxel replacement accounting. Existing runtime fields uniquely
  resolve a two-member voxel becoming one member, so no runtime trace change
  was required.
- Query summaries remain 155--165 and detailed tokens are exactly 156--158.
- Degen targeted tests passed 16/16; full pytest passed 1182 with one skip.
- FAST source and binary were unchanged; no FAST build or FAST test was run.

## Real replay evidence

Run 1 recorded 491/491 LiDAR callbacks, 9953/9953 IMU callbacks, 487 compact
observations, 2407 query summaries, and 20823 detailed traversal tokens. All
293 scan-157 formal queries have nonempty detailed tokens. Query overflow and
shadow-accounting failures are zero.

The frozen wrapper then attempted to convert the `schema_version` field in
`day8_query_overflow_summary.json` to an integer and exited with:

`invalid literal for int() with base 10: 'day8_query_overflow_summary_v1'`

No Python, schema, classifier, or Gate was changed after the active runtime
lock. No hotfix was applied, and no additional replay was started.

## Scientific boundary

The required four-run matrix and six pair comparisons do not exist. Therefore
formal completeness reproduction, expected-member path witness, root-cause
classification, and Day 9 recommendation are all incomplete or false.

`FORMAL_IKDTREE_BUG_PROVEN=false` and `DATA_RACE_PROVEN=false`.
Shadow replay is offline-only and never participates in FAST-LIO2 decisions.
Read-only instrumentation may perturb timing. Detector, ODI/AIS, weak
direction, feedback, GT, commit, and push were not used. Day 9 remains
unauthorized and requires a separate GPT audit after a newly authorized run.
