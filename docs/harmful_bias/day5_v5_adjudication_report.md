# Day 5 V5 adjudication correction and route closure

## Outcome

The frozen V5 evidence confirms a counter-semantics error. The field
`clock_duplicate_count` accumulated both bag-phase and tail-phase observations,
but the V5 finalizer treated its value 226 as proof of duplicate tail clocks.
The tail source and boundary values independently derive zero tail duplicates
and zero tail backward steps.

- `ORIGINAL_FAILURE_CLASSIFICATION=TAIL_CLOCK_DUPLICATE_TIME`
- `ORIGINAL_FAILURE_CLASSIFICATION_VALID=false`
- `ORIGINAL_FAILURE_CLASSIFICATION_INVALID_REASON=MIXED_BAG_AND_TAIL_CLOCK_DUPLICATE_COUNTER`
- `CORRECTED_EXECUTED_RUN_RESULT=PASS`
- `CORRECTED_FAILURE_CLASSIFICATION=ADJUDICATION_COUNTER_SEMANTICS_ERROR`
- `CORRECTED_FULL_MATRIX_RESULT=NOT_EVALUATED_INCOMPLETE_MATRIX`

This does not change the overall V5 Gate:

- `DAY5_STARTUP_SYNC_V5_PASS=false`
- `DAY5_RUNTIME_EQUIVALENCE_PASS=false`
- `DAY6_QUICK_DIAGNOSTICS_AUTHORIZED=false`

## Frozen evidence

Source V5 audit alias:
`$HOME/Degen-LIO-multihyp-D5-startup-sync-v5-audit.tar.gz`

SHA-256:
`9ffba9f490153fe0d95c98b4f905816f499d673427b8e87255b268546a00349a`

The gzip stream was valid and all 461 internal `SHA256SUMS` entries passed.
All 18 adjudication evidence roles resolved to one exact path with zero
ambiguity and parsed successfully. The full V5 archive is not copied into the
new adjudication package.

## Clock correction

The frozen handoff recorded:

| Field | Value |
| --- | ---: |
| original mixed duplicate count | 226 |
| original mixed backward count | 0 |
| publisher overlap count | 0 |
| last bag clock | 1600270417569223231 |
| tail first clock | 1600270417570223231 |
| tail step | 1000000 |
| expected tail first clock | 1600270417570223231 |
| first difference | 0 |
| publish count | 10383 |
| tail final clock | 1600270427952223231 |
| expected tail final clock | 1600270427952223231 |
| final difference | 0 |
| derived tail duplicate count | 0 |
| derived tail backward count | 0 |

The derivation is
`DERIVED_FROM_LOCKED_GENERATION_RULE_AND_BOUNDARY_VALUES`; it is not a claim of
individual inspection of all 10,383 published messages.

## Executed-run Gates

For the only executed run, `avia_quick_shack/AUDIT_ONLY_R1`:

- tail handoff: pass after counter-semantics correction;
- tail monotonicity: pass;
- no publisher overlap: pass;
- all callbacks and endpoint stamps received: pass;
- end-of-stream drain: pass;
- main-loop progress: pass, heartbeat 39,589 to 57,473;
- normal shutdown: pass;
- runtime products: pass from the raw run, final-map, and tap-export summaries.

The runtime-product adjudication is at the executed-run level. The original V5
six-run aggregate product Gate remains false because five runs were never
executed.

## Matrix status

- executed replays: 1;
- required replays: 6;
- pair comparisons: 0;
- full matrix: `NOT_EVALUATED`;
- Quick repeatability: `NOT_EVALUATED_INCOMPLETE_MATRIX`;
- Outdoor repeatability: `NOT_EVALUATED_INCOMPLETE_MATRIX`;
- `QUICK_BASELINE_REPEATABILITY_PASS=false`;
- `OUTDOOR_BASELINE_REPEATABILITY_PASS=false`;
- `BASELINE_REPEATABILITY_PASS=false`.

## Route and fallback

The strict cross-process bitwise route is formally closed:

- `STRICT_CROSS_PROCESS_REPLAY_ROUTE_STATUS=ABANDONED_AFTER_V5`
- `STRICT_REPLAY_FURTHER_REMEDIATION_AUTHORIZED=false`
- `CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`

No V6 was created. The replacement protocol is frozen but not executed:
in-call immutability, a frozen real observation record, offline production
detector determinism, and real-replay functional/statistical tolerance.

## Final adjudication Gate

- `ADJUDICATION_EVIDENCE_RESOLUTION_PASS=true`
- `MIXED_CLOCK_COUNTER_CONFIRMED=true`
- `TAIL_FIRST_FORMULA_PASS=true`
- `TAIL_FINAL_FORMULA_PASS=true`
- `EXECUTED_RUN_GATE_CORRECTION_PASS=true`
- `FULL_MATRIX_STATUS_CORRECTION_PASS=true`
- `STRICT_ROUTE_CLOSURE_PASS=true`
- `FALLBACK_PROTOCOL_FREEZE_PASS=true`
- `DAY5_V5_ADJUDICATION_PASS=true`

The adjudication Gate means the correction package is internally supported. It
does not authorize Stage 3, Day 6, FAST-LIO2 integration, patent action, risk
warning, public disclosure, or fallback execution. Stage 2 remains
`FAIL/PIVOT`, harmful-bias online detectability is not evaluated here, and
formal Degen-LIO remains incomplete.
