# PCL Backend Qualification v3

## Decision

Test A, Test B, and Test C all PASS under the prospectively frozen v3
rotation-metric protocol. Both nondegenerate results pass the raw rotation
matrix quality gate, and the independent C++ Eigen / Python NumPy projected
`atan2` errors agree within `1e-10` rad. Therefore
`PCL_BACKEND_IMPLEMENTATION_VALID=true` and
`PCL_BACKEND_PHASE_A_QUALIFICATION_AUTHORIZED=true`. This authorizes only a
future Phase A protocol and run; neither Phase A nor Phase B was executed.

## Immutable v2 result and archive

v2 remains A=PASS, B=FAIL, C=PASS, implementation-valid=false, and Phase A
unauthorized. Its report is unchanged; it is not retrospectively rewritten as
PASS. Tag `archive/zero-perturbation-pcl-backend-qualification-v2-fail` points to `f43c11f615a9b03c9e20bd80fcbf2b6c604b5d35`. Bundle `/home/lj/zero_perturbation_pcl_backend_qualification_v2_fail_f43c11f.bundle` has
SHA-256 `7d7e53669718a61e099182440b7a340bc4cab109a24bb9fd2fab36bce77dacc2`.

The v2 failure is classified as raw trace/acos gate failure on a near-SO(3)
matrix, requiring a separate metric-validity audit. That classification does
not alter the v2 decision.

## Full-precision v2 rotation audit

Raw Test B rotation:

```text
0.99994820356369019 0.0087264133617281914 0.0052359639666974545
-0.0087447548285126686 0.99995571374893188 0.0034906044602394104
-0.0052052712999284267 -0.0035362106282263994 0.99998015165328979
```

`R_est^T R_est` is `[[0.9999999753965678, 7.442030922717377e-10, 2.983162813996465e-10], [7.442030922717377e-10, 1.0000000845349026, 6.200826106923796e-10], [2.983162813996465e-10, 6.200826106923796e-10, 0.9999999033386948]]`. Orthogonality defect
is `1.3075527226247165e-07` and determinant is
`0.9999999816350786`. The raw trace/acos error is
`0.0001355172291302067` rad. Reflection-safe Eigen SVD
gives projection correction `6.53776363429221e-08` and formal
projected atan2 error `3.348782239246911e-09` rad. The Python value
is `3.3487821683052786e-09` rad; absolute C++/Python
difference is `7.094163232227006e-17` rad.

## Test A — NONDEGENERATE_IDENTITY

PASS. Final transform:

```text
1 1.7658956241728418e-10 1.392847059911162e-09 8.0832485149784361e-10
-1.7658956241728418e-10 1 -4.572499323618473e-10 -7.4958522722212706e-10
-1.392847059911162e-09 4.572499323618473e-10 1 -9.713473358985425e-10
0 0 0 1
```

Translation update is `1.4692796979076661e-09` m and formal
rotation update is `1.4765786192296022e-09` rad. Correspondences:
806. Source normals finite/zero/NaN are
806/0/
0; target values are
806/0/
0.

## Test B — KNOWN_SMALL_TRANSFORM

PASS. Frozen source-to-target truth:

```text
0.99994821583354732 0.0087264158771844999 0.0052359638314195796 -0.0099820327557343727
-0.0087447585619622945 0.99995567145970832 0.0034906035662378124 0.019981842907826657
-0.0052052712704045382 -0.0035362100477866485 0.99998019998872945 -0.030018077487913568
0 0 0 1
```

Estimate:

```text
0.99994820356369019 0.0087264133617281914 0.0052359639666974545 -0.0099820345640182495
-0.0087447548285126686 0.99995571374893188 0.0034906044602394104 0.019981842488050461
-0.0052052712999284267 -0.0035362106282263994 0.99998015165328979 -0.030018072575330734
0 0 0 1
```

Translation error is `5.251625722670734e-09` m and formal
projected atan2 rotation error is `3.348782239246911e-09` rad,
both below the unchanged `1e-4` thresholds. Source normal
finite/zero/NaN=806/
0/0; target=
806/0/
0.

## Test C — PLANAR_DEGENERACY_DIAGNOSTIC

PASS as a diagnostic. Point-cloud rank is 2,
point-to-plane Jacobian/Hessian rank is 3,
eigenvalues are `[0.0, 0.0, 0.0, 3.359999963045121, 3.359999963045123, 64.0]`, condition is
`RANK_DEFICIENT`, and rank-deficient is
`true`. Convergence and rotation quality are not
Test C gates.

## Frozen inputs, parameters, and scope

ICP parameter differences=0;
normal parameter differences=0;
fixture differences=0; truth
transform differences=0.
PCL remains 1.15.1. Development/Confirmatory seed access count is 0. Open3D,
Native, ODI, d50, FAST-LIO2 and the scene generator are unchanged. No third
backend, parameter rescue, Phase A/B execution, or push occurred. The final
local commit is required to leave the worktree clean.

The first CTest invocation exited in verifier initialization because the
isolated PCL Python lacked PyYAML; it reached no registration CLI. After
removing that unrelated package-level import, the one actual A/B/C execution
passed all three tests. The run manifest records both invocations and actual
microtest execution counts explicitly. The final full Python suite in the
frozen `degen-lio-zprm-py311` environment completed with 1559 passed, 1
skipped, and 0 failed. An earlier system-Python invocation is recorded as an
environment-invalid attempt because it supplied Open3D 0.13.0 instead of the
frozen 0.19.0 build.
