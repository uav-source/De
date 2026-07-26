# Fallback read-only evidence protocol V1

## Status and authorization

This document freezes the evidence protocol only:

- `FALLBACK_PROTOCOL_FROZEN=true`
- `FALLBACK_EXECUTION_AUTHORIZED=false`
- `DAY5_FALLBACK_IN_CALL_IMMUTABILITY_AUTHORIZED=PENDING_GPT_REVIEW`
- `DAY6_QUICK_DIAGNOSTICS_AUTHORIZED=false`
- `CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`

No fallback experiment is executed by this adjudication. The first fallback
item may begin only after GPT reviews the adjudication audit.

## A. In-call immutability

Within one FAST-LIO2 measurement call, compare the values immediately before
and after the read-only tap call:

- state checksum;
- covariance checksum;
- native Jacobian checksum;
- innovation checksum;
- geometric residual checksum;
- correspondence checksum;
- map size.

Every value must remain unchanged. The target Gate is
`TAP_IN_CALL_IMMUTABILITY_PASS`. This evidence does not depend on
cross-process repeatability.

## B. Frozen real observation record

Freeze one complete observation-record set from a real Quick replay with:

- schema and lifecycle;
- source commit;
- bag SHA-256;
- record SHA-256;
- no-GT audit;
- record-completeness evidence.

The target Gate is `FROZEN_REAL_OBSERVATION_RECORD_PASS`. The record is
engineering Development evidence only and must not be relabeled as Holdout or
Future Test evidence.

## C. Offline production-detector determinism

Run the production detector on the frozen observation record at least three
times using the same config and lock. Require identical output checksums and an
unchanged input checksum. The target Gate is
`OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_PASS`.

## D. Real-replay functional/statistical tolerance

Real replay may report only:

- record completeness;
- nonfinite and drop counts;
- detector runtime;
- ODI and direction-output distributions;
- functional stability;
- preregistered statistical tolerances.

It must not claim bitwise replay equivalence. Every disclosure must retain:

`CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`
