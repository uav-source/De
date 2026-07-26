# Strict cross-process replay route closure

## Decision

- `STRICT_CROSS_PROCESS_REPLAY_ROUTE_STATUS=ABANDONED_AFTER_V5`
- `STRICT_REPLAY_FURTHER_REMEDIATION_AUTHORIZED=false`
- `CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`
- `DAY5_STARTUP_SYNC_V5_PASS=false`

No V6 may be created. Continuing the same strict cross-process bitwise replay
remediation under another name is also unauthorized.

## Established by the executed V5 run

- The endpoint contract can be frozen.
- Paused start works.
- The LiDAR/IMU bidirectional handshake works.
- Tail-clock publication can continue FAST-LIO2 main-loop progress after bag
  exit.
- Callback counts and final callback stamps reach the frozen clip endpoint.
- End-of-stream drain completes.
- FAST-LIO2 performs normal shutdown without forced termination.
- Runtime summaries and the final map product complete.
- The one executed run does not prove a tail-clock duplicate. Its recorded
  duplicate counter mixed bag and tail phases; the locked tail generation rule
  and boundary values derive zero tail duplicates.

## Not established

- Quick three-run cross-process bitwise consistency.
- Outdoor three-run cross-process bitwise consistency.
- Tap OFF/ON cross-process bitwise consistency.
- Strict final-map consistency across different processes.
- Absence of detector-related cross-process scheduling effects.

Only `avia_quick_shack/AUDIT_ONLY_R1` executed. The full matrix status is
`NOT_EVALUATED`, with one of six replays and zero pair comparisons. The
corrected executed-run result is `PASS`; the corrected full-matrix result is
`NOT_EVALUATED_INCOMPLETE_MATRIX`. These are different adjudication levels and
must not be collapsed.

## Scientific and authorization state

- `STAGE2_GATE=FAIL`
- `TRANSITION=PIVOT`
- `STAGE3_START_AUTHORIZED=false`
- `STAGE4_START_AUTHORIZED=false`
- `PATENT2_AUTHORIZED=false`
- `FAST_LIO2_INTEGRATION_AUTHORIZED=false`
- `RISK_WARNING_AUTHORIZED=false`
- `PUBLIC_DISCLOSURE_AUTHORIZED=false`
- `DAY5_RUNTIME_EQUIVALENCE_PASS=false`
- `DAY6_QUICK_DIAGNOSTICS_AUTHORIZED=false`
- `HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY5_V5_ADJUDICATION`

Formal Degen-LIO remains incomplete.
