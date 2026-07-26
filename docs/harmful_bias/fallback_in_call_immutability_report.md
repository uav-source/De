# Day 5 Fallback A Same-Call Immutability Report

## Decision

`DAY5_FALLBACK_IN_CALL_IMMUTABILITY_PASS=true`

`FROZEN_REAL_OBSERVATION_RECORD_AUTHORIZED=true`

This decision is limited to same-call read-only tap immutability. It does not
prove cross-process bitwise replay equivalence and does not authorize Day 6.

## Route boundary

The strict cross-process route remains
`ABANDONED_AFTER_V5`, with
`CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN` and
`STRICT_REPLAY_FURTHER_REMEDIATION_AUTHORIZED=false`. No second process,
repeat matrix, V6, detector, ODI, AIS, eigengap, weak-direction calculation,
Development, Holdout-Dev, or Future Test was run.

The single real-data use was
`ENGINEERING_IN_CALL_IMMUTABILITY_EVIDENCE`; it was not a scientific Quick
evaluation or a detector result.

## Formal hook

The hook is in FAST-LIO2 `src/laserMapping.cpp`, symbol `h_share_model`, lines
1099-1121 at source SHA-256
`796ddeb709792a493fcbebbd91fb20a9a70f7aee9b5aef65cd83b36b9184f485`.
The formal Jacobian and innovation are complete at lines 1036-1068. The
filter update is later at line 1573 and `map_incremental()` is later at line
1589.

The pre/post boundary is:

1. hash the formal state reference, full 23×23 `kf.get_P()` covariance,
   `ekfom_data.h_x`, `ekfom_data.h`, saved signed `pd2`, accepted-index
   sidecar, formal correspondence identity, and `ikdtree.validnum()`;
2. call the existing
   `ReadonlyObservationTap::captureFirstValidMinimal`;
3. immediately hash the same formal objects again;
4. pass only checksum/map-size integers and flags to the collector.

No nearest-neighbor search, plane fit, residual/Jacobian recomputation, filter
update, or map update is introduced inside that boundary.

The formal-object checksums reuse the frozen
`RuntimeEquivalenceAudit::checksumDoubles`, `checksumUInt64s`, and
`checksumMatrix` helpers and the existing explicit formal-correspondence
serialization. The algorithm is `FNV1A64_EXACT_BYTES_V1`.

## Audit implementation

The bounded implementation is:

- `include/in_call_immutability_audit.hpp`
- `src/in_call_immutability_audit.cpp`
- `test/test_in_call_immutability_audit.cpp`

It defaults off, has no background thread, writes no file, publishes no topic,
uses no RNG, and stores only aggregate integers plus the first mismatch. The
read-only service is
`/harmful_bias/in_call_immutability_status` (`std_srvs/Trigger`) and does not
clear collector state.

The new C++ suite passed 27/27 tests; all FAST tests passed 186/186. Degen
targeted tests passed 41/41, and the full suite passed 897/897 after restoring
the repository's eight previously audited historical HOME lock files by their
recorded SHA-256 values.

## One engineering replay

Only `multihyp_fallback_in_call_v1` /
`avia_quick_shack` ran, using clip SHA-256
`272325265978787c838e010b1f0da963a15fb4b08ff8730fc3dd9901e32a0e20`.
The read-only tap was enabled with `DETECTOR_MINIMAL_V1`, capacity 1024, while
observation export and detector execution were disabled.

Observed transport evidence:

- rosbag natural exit: pass;
- TCPROS handshake: pass;
- LiDAR callbacks: 491 / 491;
- IMU callbacks: 9953 / 9953;
- end-of-stream drain: pass;
- normal FAST/roslaunch shutdown: pass;
- runtime binary trailer/checksum: pass;
- observation binary count: 0;
- tap drop count: 0.

The frozen V5 runner returned 30 after shutdown because its raw
`handoff_pass` still gates the mixed bag/tail duplicate counter (246). This is
the exact counter-semantics condition already resolved by the verified V5
adjudication archive. The independent frozen-rule recalculation for this run
found:

- start and stop success: true;
- first tail clock = last bag clock + 1,000,000 ns;
- final tail clock = first tail clock + (10,563 - 1) × 1,000,000 ns;
- publisher overlap: 0;
- backward count: 0;
- derived tail duplicate count: 0.

The offline completion therefore applies the already-authorized adjudication;
it does not change code, rerun rosbag, or revive cross-process equivalence.
Both the raw failure and corrected transport evidence are preserved.

## Same-call results

The final read-only service snapshot reports:

- audited calls: 487;
- tap attempts: 487;
- tap records emitted: 487;
- all unchanged: 487;
- mutation detected: 0;
- state mismatch: 0;
- covariance mismatch: 0;
- native Jacobian mismatch: 0;
- formal innovation mismatch: 0;
- geometric residual mismatch: 0;
- accepted-index mismatch: 0;
- formal-correspondence mismatch: 0;
- map-size mismatch: 0;
- first mismatch: null;
- nonfinite checksum inputs: 0;
- internal audit errors: 0.

There was no ground truth, pose/axis GT, or trajectory-error calculation. The
result proves only that the existing read-only tap did not change the checked
formal objects within each audited measurement-model call.

## Scientific and authorization boundary

The fixed scientific state remains:

- `STAGE2_GATE=FAIL`
- `TRANSITION=PIVOT`
- `COHERENT_BIAS_HARMFUL_MECHANISM_SUPPORTED=true`
- `COHERENT_BIAS_STABLY_ONLINE_DETECTABLE=false`
- `HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY5_FALLBACK_IN_CALL`
- `STAGE3_START_AUTHORIZED=false`
- `STAGE4_START_AUTHORIZED=false`
- `PATENT2_AUTHORIZED=false`
- `FAST_LIO2_INTEGRATION_AUTHORIZED=false`
- `RISK_WARNING_AUTHORIZED=false`
- `PUBLIC_DISCLOSURE_AUTHORIZED=false`

Passing this task authorizes only freezing a real observation record in a
future separately authorized step. It does not itself freeze or export that
record. `DAY6_QUICK_DIAGNOSTICS_AUTHORIZED=false`,
`OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_AUTHORIZED=false`, and
`REAL_REPLAY_FUNCTIONAL_STATISTICAL_TOLERANCE_AUTHORIZED=false`. Formal
Degen-LIO remains incomplete.
