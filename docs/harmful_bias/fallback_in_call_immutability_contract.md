# Fallback A Same-Call Immutability Contract

## Scope

This is a bounded engineering evidence route after the strict cross-process
bitwise replay route was abandoned after V5. It audits one real
`avia_quick_shack` replay and synthetic/unit tests. It does not compare two ROS
processes and does not reopen a replay matrix.

The only real-data use label is
`ENGINEERING_IN_CALL_IMMUTABILITY_EVIDENCE`.

## Runtime mode

The runner/manifest engineering mode is `FALLBACK_IN_CALL_AUDIT`. FAST-LIO2
uses its existing internal `CAPTURE_ONLY` switch solely to enable the read-only
tap while keeping the binary observation writer disabled:

- read-only tap: enabled;
- observation export: disabled;
- in-call audit: enabled;
- payload: `DETECTOR_MINIMAL_V1`;
- bounded tap capacity: 1024;
- detector execution: disabled;
- `CAPTURE_ONLY_EQUIVALENCE_STATUS=NOT_EVALUATED`.

This mode is not evidence for the old Stage B CAPTURE_ONLY equivalence claim.

## Audit record and bounded state

`InCallImmutabilityAudit` receives no estimator objects, matrices, residual
arrays, map handles, or correspondence containers. It receives two
`InCallChecksums` values, scan/call integer identity, first-valid/tap flags,
and two diagnostic flags. It stores aggregate counters and at most the first
mismatch record. Memory use is independent of scan count when no mismatch
occurs.

The module:

- defaults off;
- has no background thread;
- writes no file;
- publishes no topic;
- uses no random number;
- provides the read-only
  `/harmful_bias/in_call_immutability_status` `std_srvs/Trigger` service;
- never clears state from the service;
- returns `in_call_immutability_status_v1` JSON without formal payload arrays.

## Pass boundary

The final fallback pass requires one complete engineering replay, exact
endpoint callback counts, end-of-stream drain, normal shutdown, positive and
complete audited-call coverage, zero mismatch/nonfinite/internal-error/drop
counts, unchanged formal mathematics, passing tests, and an allowed diff
scope.

If and only if every gate passes:

- `DAY5_FALLBACK_IN_CALL_IMMUTABILITY_PASS=true`;
- `FROZEN_REAL_OBSERVATION_RECORD_AUTHORIZED=true`.

This does not authorize detector execution, ODI/AIS/weak-direction
calculation, Day 6, production integration, scientific quick evaluation, or
public disclosure.

Fixed regardless of result:

- `STAGE2_GATE=FAIL`
- `TRANSITION=PIVOT`
- `STAGE3_START_AUTHORIZED=false`
- `STAGE4_START_AUTHORIZED=false`
- `FAST_LIO2_INTEGRATION_AUTHORIZED=false`
- `DAY6_QUICK_DIAGNOSTICS_AUTHORIZED=false`
- `OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_AUTHORIZED=false`
- `REAL_REPLAY_FUNCTIONAL_STATISTICAL_TOLERANCE_AUTHORIZED=false`
- `STRICT_REPLAY_FURTHER_REMEDIATION_AUTHORIZED=false`
- `CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`
- `HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY5_FALLBACK_IN_CALL`
