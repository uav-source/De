# Harmful-Bias Multihyp Day 4 Detector Adapter Contract

## 1. Objective and boundary

Day 4 answers one question only: can a Day 3 read-only observation record be
mapped to the frozen production degeneration detector with exactly the same
result as a direct production call? The work is a deterministic synthetic
side-path integration audit. It is not a scientific experiment, harmful-bias
detector, runtime benchmark, or FAST-LIO2 estimator integration.

## 2. Reused Day 3 observation contract

The adapter accepts only records validated by
`validate_first_valid_observation_record()` from
`src/fastlio2_adapter/readonly_observation_schema.py`. It does not provide a
second or relaxed observation validator. The frozen observation JSON schema is
`schemas/harmful_bias/readonly_observation_v1.schema.json`, SHA-256
`c674b471ec42b583f1344466f481378ff01b3814724b3ccdc4044b48d40caca0`.

## 3. Unique production detector entrypoint

The Day 2 source map identifies exactly one per-frame production entrypoint:

```text
src/degen_detector/odi_tracker.py::compute_metrics_for_frame
lines 64-205
source SHA-256 c515e5321e569ed074ae1c4f33563e73a82775800f20197612c2816086676d17
```

Candidate count is one and ambiguity count is zero. The sequence function is a
batch wrapper around this entrypoint, not a second detector implementation.

The production metric/configuration provenance is:

```text
metric version: detector_stage2a_v1
config: configs/detector/odi_stage2a.yaml
config SHA-256: 665c3df8f794841ac5f3afe97e77f9993aaae2feaf3510043ecff6646acf2398
lock: artifacts/current/detector_stage2a/locked/detector_lock.json
lock SHA-256: 075f14217f5e9c782bc1ab4051e6533f34d4932399c7f4b8cbc60a03d62fe358
```

The adapter verifies that the source and config hashes match the frozen lock,
then reads the frozen trigger setting from that lock. It does not define,
calibrate, or copy a detector threshold.

## 4. Thin input mapping

The detector Jacobian is read directly from
`detector_pose_jacobian_rows` as an independent `float64` `N x 6` array. Its
order is already:

```text
[delta_theta_x, delta_theta_y, delta_theta_z,
 delta_p_x,     delta_p_y,     delta_p_z]
```

Day 4 performs no second `[3,4,5,0,1,2]` mapping. Translation columns are in
the WORLD frame, while rotation retains the Day 3 IMU/body-local right tangent
semantics.

The selected residual field is `formal_filter_innovation_h`. The Day 3
validator and adapter enforce `h = -pd2` within `1e-12`; only `h` enters the
canonical detector-input payload. The current production detector does not
consume residual values, but the selected field remains explicit and is not
mixed with `signed_geometric_residual_pd2`.

The input representation is `CONSTANT_SCALAR_VARIANCE`. The adapter performs
only:

```python
variance = np.full(N, measurement_variance_scalar_m2, dtype=np.float64)
```

It does not invert, square-root, or replace the variance with per-point
confidence. `prior_covariance_detector_order` is validated as part of the Day 3
record but is not used by the production detector and is never added to the
point-to-plane information.

## 5. No duplicated detector mathematics

`src/fastlio2_adapter/detector_adapter.py` contains no information-matrix,
spectral, ODI, AIS, Schur, condition-number, weak-direction, eigengap, Huber, or
threshold formula. It validates and copies inputs, invokes
`compute_metrics_for_frame`, maps the returned fields, computes canonical
SHA-256 checksums, and validates the output structure.

## 6. Output schema and direction semantics

Outputs conform to
`schemas/harmful_bias/readonly_detector_output_v1.schema.json`. It records
input, detector-input, and detector-output checksums; detector provenance;
translation diagnostics; primary weak direction; and trigger/direction state.
The weak direction frame is fixed to `WORLD`, and `synthetic_only` is fixed to
true for Day 4.

Invalid outputs use JSON `null` for detector numeric/direction results and
false for direction/trigger booleans, together with a closed `invalid_reason`.
The validator checks structure and consistency only; it does not recompute any
detector result.

The production weak-direction implementation already normalizes the selected
minimum-eigenvalue vector and applies its own canonical sign rule. The adapter
returns that vector unchanged and never performs sign normalization.

## 7. Direct equivalence

For each fixture, the audit independently forms `J` and scalar-expanded
`R_diag`, directly calls `compute_metrics_for_frame`, and compares that result
with the adapter result. Scalars, translation spectrum, direction, and state
booleans use an absolute tolerance of `1e-12`; current outputs are elementwise
identical with maximum error zero.

## 8. Input immutability and determinism

The canonical observation SHA-256 and complete nested record are compared
before and after every adapter call. Jacobian, both residual arrays, variance,
prior pose/covariance, accepted indices, proxy IDs, planes, and neighbors must
remain byte-equivalent. Arrays passed to production are independent copies.

Each fixture is evaluated three times. No runtime field is emitted, and the
three canonical output SHA-256 values must be identical.

## 9. Deterministic synthetic fixtures

The non-random fixtures are `well_conditioned`, `weak_x`, and `weak_rotated`.
They use full-rank pose Jacobians, finite residuals, and the same scalar
variance contract. Axis-alignment expectations exist only in tests and never
appear as online fields. The fixture records are generated from fixed numeric
construction; they are not extracted from a bag, evaluation sequence, or
reserved dataset.

These fixtures prove mapping and production-call equivalence only. They do not
measure AUROC, operating performance, harmful-bias detectability, or scientific
superiority.

## 10. Causality and frozen artifacts

The adapter signature accepts one observation mapping only. Production paths
read no GT pose/axis, labels, later frames, trajectory error, map state, or
evaluation partition information. The adapter writes no files and publishes no
ROS topic; only the explicitly invoked synthetic runner writes synthetic audit
artifacts.

The 16-file `artifacts/current/detector_stage2a` tree is hashed before and
after Day 4. Its ordered digest remains
`4b34576a1acb49d50ccceb54dc76c3aa86ea41c80bbb238e11d18f1c209352de`.
No detector source, lock, configuration, threshold, or Development statistic
is modified.

## 11. Day 5 boundary

If every Day 4 gate passes, `DAY5_RUNTIME_EQUIVALENCE_AUTHORIZED=true` permits
only the next Quick-bag detector OFF/ON equivalence audit. It does not authorize
Stage 3, a filter update modification, multi-hypothesis logic, harmful-bias
detectability claims, or complete Degen-LIO integration.

Day 4 has not run an OFF/ON rosbag comparison. Its fixed status is
`OFF_ON_REPLAY_EQUIVALENCE_STATUS=NOT_RUN_DAY4`.
