# Day 6 Fallback Branch-Divergence Root-Cause Audit Contract

## Authorization and identity

This is a pure offline audit of the already frozen Day 6 Fallback functional
diagnostics evidence. The accepted input is the final delivery archive whose
SHA-256 is
`a6fad908751adf527812ad2cad5ed497c1f2190dff20f5549e41ef3c36eab61a`.
The earlier SHA-256
`bf15339f89860438e842b8e37cdfe9ed693fe942e8dac13ed54aa4134413f61f`
is retained only as the pre-permission-normalization lineage identity.

The accepted change classification is
`ARCHIVE_ROOT_PERMISSION_NORMALIZATION`: the archive root changed from mode
`0775` to `0755`. No scientific-payload change is authorized. Acceptance
therefore requires the final outer SHA, valid gzip, normalized member modes,
zero links, zero internal checksum failures, all three frozen observation
identities, all fixed lifecycle counts, and all original Day 6 gate
conclusions.

## Execution boundary

The audit may parse existing compact observations, compare their formal
numerical semantics, reconstruct translation information through the locked
production matrix helpers, calculate descriptive eigenspace statistics,
inspect frozen FAST-LIO2 source, render engineering-diagnostic plots, run pure
offline tests, and package the resulting evidence.

It may not run ROS, FAST-LIO2, rosbag, a new replay, or the production detector
entrypoint. It may not alter any observation, FAST-LIO2 source, production
detector source, configuration, lock, threshold, schema, existing Day 1-6
manifest, strict-route closure, frozen reference, or README. It may not create
a commit or push.

## Semantic comparison contract

`SEMANTIC_OBSERVATION_V1` contains scan and measurement-call identity, begin/end
timestamps, prior pose and covariance, the scalar measurement variance and
representation, valid-correspondence count, detector-order pose Jacobian,
formal innovation, and formal measurement/correspondence checksums.

Run identifiers, process/path metadata, output seals, binary framing checksums,
record self-checksums, and creation metadata are excluded from semantic
identity. Any change to a retained formal field must change the semantic
checksum.

The first divergence is the earliest record whose retained semantics differ.
The prior record is checked explicitly. Divergence order is restricted to:

- `PRIOR_STATE_ALREADY_DIVERGED`
- `MEASUREMENT_OR_CORRESPONDENCE_DIVERGED_WITH_EQUAL_PRIOR`
- `SAME_RECORD_ORDER_UNRESOLVED`
- `INSUFFICIENT_RECORD_GRANULARITY`

Checksums prove aggregate byte-level difference or equality only for the
encoded object. They do not disclose the responsible accepted index, plane,
point, nearest neighbor, map element, or scheduling event.

## Evidence-granularity contract

Every proposed evidence item is classified as
`AVAILABLE_AND_VALIDATED`, `CHECKSUM_ONLY`, `NOT_RECORDED`, or
`NOT_APPLICABLE`. Missing raw LiDAR, IMU-bundle, undistorted-cloud, map-content,
map-insertion-order, full correspondence, nearest-neighbor, OpenMP, or thread
traces must remain explicit. A checksum-only item cannot support an
array-element identity claim.

Static source inspection may establish that parallel, tree, map, measurement,
and filter paths exist. It cannot by itself prove a data race, scheduling
causality, map causality, or tree-order causality.

## Information and eigenspace contract

For each production-domain record, the audit reconstructs the normalized
translation Schur information using the locked production helper functions and
compares eigenvalues, primary weak direction modulo sign, ODI, AIS, minimum
eigenvalue, and condition number against the frozen direct output.

Direction angles use `abs(v_a dot v_b)`. Two-dimensional weak-subspace
stability uses principal angles between the spans of the two weakest
eigenvectors. Gap, perturbation, time-adjacent, and cross-run calculations are
descriptive. Correlations carry `causal_interpretation=false`; no threshold is
introduced.

Near-multiple eigenvalues may explain instability of a chosen weak
eigenvector. That observation cannot automatically explain the upstream FAST
trajectory or formal-measurement branch.

## Hypothesis and conclusion boundary

H1-H10 statuses are restricted to `SUPPORTED`, `PARTIALLY_SUPPORTED`,
`CONTRADICTED`, `PLAUSIBLE_UNPROVEN`, or `NOT_OBSERVABLE`, with bounded
confidence and explicit supporting, contradicting, and missing evidence.

The audit may mark branch localization complete when the frozen record evidence
supports it. `FAST_BRANCH_ROOT_CAUSE_PROVEN` must remain false while direct
input, map/order, neighbor, or scheduling evidence required for a mechanism is
missing. Audit completeness cannot turn an unobserved mechanism into a cause.

## Gate and phase boundary

`DAY6_BRANCH_DIVERGENCE_ROOT_CAUSE_AUDIT_PASS` requires every identity,
comparison, localization, granularity, source, environment, reconstruction,
eigenspace, hypothesis, limitation, next-experiment-design, plot, test, diff,
and package-scope gate to pass.

Even when the audit gate passes:

- `NEXT_DIAGNOSTIC_EXPERIMENT_AUTHORIZED=false`
- `STAGE2_GATE=FAIL`
- `TRANSITION=PIVOT`
- `STAGE3_START_AUTHORIZED=false`
- `FAST_LIO2_INTEGRATION_AUTHORIZED=false`
- `CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`
- `HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY6_BRANCH_DIVERGENCE_ROOT_CAUSE`

The next minimal experiment may be recommended by information gain, but it
requires separate authorization.
