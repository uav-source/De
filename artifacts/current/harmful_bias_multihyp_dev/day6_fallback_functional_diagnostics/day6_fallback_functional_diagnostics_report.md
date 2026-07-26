# Day 6 Fallback Functional Diagnostics Report

## Outcome

`DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_PASS=true`.

This is Day6-Fallback, not the original strict cross-process bitwise Day 6. The strict route remains closed and `CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`.

## Execution boundary

Three new Quick Shack replays ran sequentially with fresh ROS masters. Each replay used the locked read-only tap, compact export, in-call immutability audit, frozen tail adjudication, drain, and normal shutdown flow.

The production detector ran only after each replay in a new locked Python process. It was a read-only shadow diagnostic and did not feed FAST-LIO2 state, covariance, residuals, gain, map, or control.

## Per-run lifecycle and detector completeness

| run | raw rc | raw handoff | adjudicated | LiDAR | IMU | observations | adapter/direct |
|---|---:|---|---|---:|---:|---:|---:|
| multihyp_day6_fallback_quick_r1 | 30 | false | true | 491 | 9953 | 487 | 487/487 |
| multihyp_day6_fallback_quick_r2 | 30 | false | true | 491 | 9953 | 487 | 487/487 |
| multihyp_day6_fallback_quick_r3 | 30 | false | true | 491 | 9953 | 487 | 487/487 |

Raw handoff fields were preserved. The frozen V5 rule was applied only to mixed bag/tail counters; raw runner exit codes were not rewritten.

## Continuity and descriptive characterization

Every observation has one adapter output and one direct diagnostic output. Production-domain metric mismatches and adapter-precondition contract mismatches are zero. Output timestamps are monotonic, scan identities are continuous, and there are no missing or duplicate outputs.

Weak-direction continuity uses the sign-invariant angle `acos(abs(dot(u_t,u_t-1)))`. Null and unstable directions are excluded from angle statistics but retained in record and flag counts. Flag transitions and detector metrics are reported descriptively.

Latency is `POST_REPLAY_OFFLINE_LOCKED_ENVIRONMENT_ONLY`; it does not represent online end-to-end, FAST-LIO2 real-time, or control-loop latency.

Frozen-reference and pairwise cross-run comparisons align by `scan_index`, `timestamp_begin`, and `timestamp_end`. Exact output equality is not required, and no bitwise Gate is restored even if values happen to coincide.

## Scientific limitations

This task has no ground truth and does not evaluate detector accuracy, scientific effectiveness, or harmful-bias detectability. It does not compute AUROC, AUPRC, FPR, or recall, and it does not run Development, Holdout, or Future Test.

`STAGE2_GATE=FAIL`, `TRANSITION=PIVOT`, `STAGE3_START_AUTHORIZED=false`, `FAST_LIO2_INTEGRATION_AUTHORIZED=false`, and `NEXT_PHASE_AUTHORIZED=false` remain fixed. A separate GPT authorization is required for any next phase.

## Identity

- Main run: `multihyp_day6_fallback_functional_diagnostics_v1`
- FAST binary SHA-256: `5af22373f923eea39d63c055fc0b2dd6353926fbe5a29535a1a35c7d453c1cc3`
- Detector/config/lock SHA-256: `c515e5321e569ed074ae1c4f33563e73a82775800f20197612c2816086676d17` / `665c3df8f794841ac5f3afe97e77f9993aaae2feaf3510043ecff6646acf2398` / `075f14217f5e9c782bc1ab4051e6533f34d4932399c7f4b8cbc60a03d62fe358`
