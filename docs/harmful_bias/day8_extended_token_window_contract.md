# Day 8 Extended Detailed Token Window Contract

## Scope

This run is an internal engineering range-query path diagnostic. It extends
only the existing detailed traversal-token capture window from scans 156--158
to scans 156--163 while preserving the query-summary window at 155--165.

FAST-LIO2 source, `Search_by_range`, range relations, pruning, child order,
result collection, deletion visibility, rebuild behavior, map updates, thread
configuration, CPU affinity, and the existing binary are immutable.

## Authorization

- Main run: `multihyp_day8_extended_detailed_token_window_v1`
- New runs: `multihyp_day8_extended_token_r1` through `r4`
- ROS master ports: 20811 through 20814
- FAST CPU: 22
- rosbag CPU: 23
- playback rate: 0.25
- Exactly four new Quick Shack replays; prior runs cannot be reused.
- No fifth replay and no post-lock analysis or parameter hotfix.

## Token semantics

All new outputs use `TOKEN_CAPTURE_SEMANTICS_V2`.

The only capture states are:

- `CAPTURED_NONEMPTY`
- `CAPTURED_EMPTY_FORMAL_QUERY`
- `NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW`
- `NOT_CAPTURED_TRACE_DISABLED`
- `CAPTURE_FAILED`
- `OVERFLOWED`

Any `NOT_CAPTURED` side makes token comparison `NOT_APPLICABLE`,
`token_sequence_equal` JSON `null`, the final taxonomy `EVIDENCE_GAP`, and the
detailed classification
`EVIDENCE_GAP_DETAILED_TRACE_NOT_CAPTURED`. Missing capture is never an empty
trace. `CAPTURE_FAILED` and `OVERFLOWED` fail the execution gate.

## Claim boundary

Even a fully witnessed formal completeness difference is reported only as
`FORMAL_RANGE_QUERY_COMPLETENESS_VIOLATION_OBSERVED_UNDER_INSTRUMENTED_REPLAY`.
It does not prove a production iKD-tree bug or data race. Read-only
instrumentation can perturb timing. Shadow replay is offline and never
participates in FAST decisions.

The fixed states remain:

- `STAGE2_GATE=FAIL`
- `TRANSITION=PIVOT`
- `STAGE3_START_AUTHORIZED=false`
- `STAGE4_START_AUTHORIZED=false`
- `FAST_LIO2_INTEGRATION_AUTHORIZED=false`
- `FORMAL_IKDTREE_BUG_PROVEN=false`
- `DATA_RACE_PROVEN=false`
- `DAY9_AUTHORIZED=false`

Day 9 can only be recommended by the frozen gate and still requires a separate
GPT audit before authorization.
