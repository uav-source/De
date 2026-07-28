# Zero-Perturbation PCL Backend Qualification v3

Status: prospectively frozen before implementing or executing v3. Protocol
type: `rotation_metric_validity_requalification`.

v3 changes only the numerical validity of the rotation-error measurement. PCL
1.15.1, every ICP and normal parameter, all A/B/C inputs, Test B truth and both
error thresholds remain byte-for-byte or value-for-value identical to v2.
Open3D, Native, ODI, d50, FAST-LIO2, scene generators and seed schedules are
outside scope. Phase A and Phase B are unauthorized before and during v3.

## Immutable v2 result

The archived v2 commit is `f43c11f615a9b03c9e20bd80fcbf2b6c604b5d35`,
tagged `archive/zero-perturbation-pcl-backend-qualification-v2-fail`. Its
bundle SHA-256 is
`7d7e53669718a61e099182440b7a340bc4cab109a24bb9fd2fab36bce77dacc2`.
The v2 outcomes remain A=PASS, B=FAIL, C=PASS,
`PCL_BACKEND_IMPLEMENTATION_VALID=false`, and Phase A unauthorized. v3 never
rewrites that report.

v2 is reclassified as a raw trace/acos gate failure on a matrix that is near,
but not exactly on, SO(3). This makes rotation metric validity require a
separate audit; it does not retrospectively make Test B pass.

## Full-precision v2 observation

The v2 raw Test B JSON, not the rounded report matrix, records:

```text
0.9999482035636902    0.008726413361728191   0.0052359639666974545
-0.008744754828512669 0.9999557137489319     0.0034906044602394104
-0.005205271299928427 -0.0035362106282263994 0.9999801516532898
```

Its orthogonality defect is `1.3075527226247165e-7`, determinant
`0.9999999816350786`, projection correction `6.537763624716303e-8`, raw
trace/acos argument `0.9999999908175403`, and raw error
`1.355172291302067e-4` rad. A reflection-safe nearest-SO(3) projection followed
by the prospective atan2 metric gives the pre-run diagnostic
`3.34878216948272e-9` rad. Only the v3 execution may determine the v3 gate.

## Reflection-safe nearest SO(3)

For `R_raw = U Sigma V^T`, v3 defines
`D = diag(1, 1, sign(det(U V^T)))` and
`R_projected = U D V^T`. A bare `U V^T` is forbidden. The projected
determinant must be positive. Truth is independently checked to be finite,
orthogonal and positive-determinant, but never altered.

Projection cannot hide an invalid estimate. Before projected error is used,
v3 requires a finite raw matrix, positive determinant, Frobenius orthogonality
defect at most `1e-5`, absolute determinant error at most `1e-5`, and projection
correction at most `1e-5`. Failure of any item fails Test A or B directly.

## Formal atan2 error and crosscheck

For `R_error = R_truth^T R_projected`, v3 computes clipped trace cosine and the
half-norm of the skew-vector sine, then uses `atan2(sin_theta, cos_theta)`.
Unprojected trace/acos remains diagnostic only.

Every gated A/B result is evaluated independently by C++ Eigen JacobiSVD and
Python NumPy SVD implementations. Their projected atan2 errors must differ by
at most `1e-10` rad. A mismatch stops v3; selecting the smaller result is
forbidden.

## Frozen tests and stopping rule

Only the existing NONDEGENERATE_IDENTITY, KNOWN_SMALL_TRANSFORM, and
PLANAR_DEGENERACY_DIAGNOSTIC inputs may run, once each in the v3 CTest run.
Test A retains `1e-8` translation/rotation thresholds. Test B retains `1e-4`
translation/rotation thresholds. Test C remains rank-deficiency-only and does
not require convergence.

Implementation validity and future Phase A authorization require all three
tests, both rotation matrix quality gates, the C++/Python crosschecks, and all
parameter/fixture/truth/seed firewalls to pass. Even a passing v3 authorizes
only a future Phase A protocol and run; v3 itself executes neither Phase A nor
Phase B and substitutes no third backend.
