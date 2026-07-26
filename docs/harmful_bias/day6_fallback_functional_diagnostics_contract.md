# Day 6 Fallback Functional Diagnostics Contract

## Identity

This contract authorizes `DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS`, not the
original strict cross-process bitwise Day 6 route. The strict route remains
`ABANDONED_AFTER_V5`, and cross-process bitwise replay equivalence remains
`NOT_PROVEN`.

The only replay input is the fixed `avia_quick_shack` clip. Three new runs are
executed sequentially with independent ROS masters. FAST-LIO2 uses the already
locked read-only observation tap, compact binary writer, in-call immutability
audit, tail clock, drain, and normal shutdown flow. No FAST-LIO2 source or
binary rebuild is authorized.

## Shadow detector boundary

The production detector is not called inside FAST-LIO2. Each completed replay
is shut down before a new locked Python process reads the compact observation
binary in original order. The process emits both the canonical adapter stream
and a direct-production diagnostic stream.

Detector output never changes estimator state, covariance, gain, residuals,
correspondences, map contents, filtering, propagation, or control. Recorded
latency is only post-replay production-call latency in the locked environment;
it is not online, end-to-end, real-time, or control-loop latency.

## Engineering diagnostics

Required checks cover callback and lifecycle completion, binary integrity,
record and detector-output completeness, input immutability, adapter/direct
contract behavior, timestamp and scan continuity, sign-invariant weak-direction
angles, flag transitions, descriptive metric distributions, descriptive
latency distributions, frozen-reference alignment, and pairwise cross-run
alignment.

No cross-run exact-output gate is applied. Statistical differences are
descriptive and have no acceptance threshold.

## Scientific boundary

The observations have no ground-truth role. `degeneracy_triggered` is a
detector output flag, not a ground-truth label. This task does not compute
AUROC, AUPRC, FPR, recall, or detector accuracy, and it does not evaluate
scientific effectiveness or harmful-bias detectability.

`STAGE2_GATE=FAIL`, `TRANSITION=PIVOT`, and all Stage 3, Stage 4, FAST-LIO2
integration, patent, risk-warning, and public-disclosure authorizations remain
unchanged. A passing engineering diagnostic may recommend another review, but
`NEXT_PHASE_AUTHORIZED=false` remains fixed.
