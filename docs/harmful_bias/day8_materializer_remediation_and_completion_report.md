# Day 8 Overflow Materializer Remediation and Four-Run Completion Report

## Outcome

The offline overflow materializer defect is fixed and verified. Immutable run 1
was rematerialized without ROS, rosbag, or FAST-LIO2, and all 68 copied runtime
input files retained identical sizes and SHA-256 values. Exactly three new real
replays (r2, r3, and r4) completed their explicitly authorized per-run gates,
forming four effective runs and six run-pair comparisons.

The overall Day 8 execution gate remains **false**. The first formal result
difference for each pair involving reused r1 is at scan 162, while detailed
tokens were frozen only for scans 156--158. Consequently, those three pairs are
classified `EVIDENCE_GAP`; no locked evidence can establish the first divergent
token, the missing point's visit/skip path, or the range-search context root
cause. The three pairs among new r2--r4 reproduce no formal range-search
difference.

Fixed scientific status:

- `STAGE2_GATE=FAIL`
- `TRANSITION=PIVOT`
- `FORMAL_IKDTREE_BUG_PROVEN=false`
- `DATA_RACE_PROVEN=false`
- `DAY8_MATERIALIZER_REMEDIATION_EXECUTION_PASS=false`
- `DAY8_IKDTREE_RANGE_SEARCH_CONTEXT_PASS=false`
- `DAY9_RECOMMENDED=false`
- `DAY9_AUTHORIZED=false`
- `STAGE3_START_AUTHORIZED=false`
- `STAGE4_START_AUTHORIZED=false`
- `FAST_LIO2_INTEGRATION_AUTHORIZED=false`

## Required answers

1. The original materialization error iterated over every JSON value and tried
   to convert `schema_version = "day8_query_overflow_summary_v1"` to an integer.
   The failure occurred after run 1 had completed its runtime capture.
2. `schema_version` is metadata, not a count. Only the four frozen overflow
   count fields can participate in the overflow sum; `schema_error_count` is
   validated and handled separately.
3. The bounded code change touched
   `scripts/113_run_day8_focused_traversal.py` and added
   `src/fastlio2_adapter/day8_overflow_summary.py`,
   `scripts/117_materialize_day8_focused_run.py`, and
   `tests/test_day8_overflow_summary_materializer.py`.
4. FAST-LIO2 source, binary, build products, tests, `Search_by_range`,
   threading, affinity, and parameters were not changed.
5. Run 1 is reusable because its ROS/rosbag/FAST capture, drain, shutdown,
   observation, query, token, snapshot, overflow, and shadow evidence had
   already completed; only the frozen offline materializer failed.
6. The before/after identity inventories contain 68 run 1 input files. Their
   canonical JSON documents have the same SHA-256,
   `798f1c9070912b4687046a47284302773c2b540795d2897761463df7b5a93842`.
7. Run 1 was not replayed. Its rematerializer reports `ros_started=false`,
   `rosbag_started=false`, `fast_started=false`, and
   `real_replay_rerun=false`.
8. r2, r3, and r4 each have wrapper exit 0; 491 LiDAR callbacks, 9953 IMU
   callbacks, 490 runtime scans, 487 observations, 11 stage records, 22
   coherent snapshots, no incoherent snapshots, no overflow/schema errors,
   no shadow accounting/closure failures, no tap/writer/mutation/GT failures,
   and passing drain, shutdown, and runtime-product gates.
9. The matrix contains four effective runs: reused
   `multihyp_day8_focused_traversal_r1` and new
   `multihyp_day8_focused_materializer_r2`, `_r3`, and `_r4`. This remediation
   consumed exactly three real replays and zero run 1 replays.
10. Every effective run has 293 scan-157 queries and 293 queries with
    nonempty detailed tokens, so scan-157 coverage is 100%.
11. Offline shadow accounting passes for all four runs with zero mutation
    delta and state-closure failures. Shadow replay never participates in FAST
    decisions.
12. r1--r2, r1--r3, and r1--r4 first differ at aligned query index 1840
    (scan 162, query sequence 1841); all are `EVIDENCE_GAP`. r2--r3, r2--r4,
    and r3--r4 are `NO_RANGE_SEARCH_DIVERGENCE_REPRODUCED`.
13. The scan-162 first differences do not have detailed tokens:
    both sides resolve to `NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW`.
14. The missing expected member is
    `317139299db85be8dfd634f0b20c8b5748bf19a5fdce8abedd2d9924315f5c99`.
    Whether it was visited cannot be determined from the captured evidence;
    zero matching token rows must not be interpreted as proof that it was not
    visited.
15. No visited-node skip reason can be stated because scan-162 tokens were not
    captured.
16. No first path difference can be stated for the same reason. Aggregate
    visited/prune/full-cover/deletion counters differ, but cannot replace a
    token-by-token path witness.
17. Pair classifications are three `EVIDENCE_GAP` and three
    `NO_RANGE_SEARCH_DIVERGENCE_REPRODUCED`; the final root-cause
    classification is `EVIDENCE_GAP_DETAILED_TRACE_NOT_CAPTURED`.
18. The shadow/formal evidence records a candidate completeness anomaly:
    the logical shadow set is the same singleton in r1 and r2, while r1's
    formal result omits it and r2 returns it. Under the task's stricter
    publication gate, `FORMAL_RANGE_QUERY_COMPLETENESS_VIOLATION_OBSERVED`
    remains false because the required detailed token evidence is absent.
19. `IKDTREE_RANGE_SEARCH_CONTEXT_ROOT_CAUSE_LOCALIZED=false`.
20. The evidence does not prove a formal ikd-tree bug.
21. The evidence does not prove a data race.
22. Read-only instrumentation may perturb timing and scheduling; this limits
    cross-process causal and bitwise claims.
23. Day 9 is not recommended from this stopped gate. A future proposal would
    need a separately authorized capture window covering the observed scan-162
    divergence; this report does not authorize such a replay.
24. Day 9 remains unauthorized because only a separate GPT audit may grant
    that authorization after reviewing the evidence gap and scope.

## Test and lock evidence

The parser regression set passed 18 tests. The requested Day 8 targeted set
passed 34 tests. Full Degen-LIO pytest passed 1200 tests with 1 skipped. The
post-lock code check found zero Python hash mismatches. The FAST binary remained
`f02f1da250bfb20e5d0c94ceaccd5b8d0824e3d32e79d359588a20e28b387167`.

No detector, ODI/AIS, weak direction, feedback, GT, commit, push, reset,
clean, stash, FAST build, or FAST test was used.
