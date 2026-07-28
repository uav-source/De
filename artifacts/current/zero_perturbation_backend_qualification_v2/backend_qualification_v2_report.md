# PCL Backend Qualification v2 — stopped decision

## Decision

The independent v2 implementation qualification **stops as FAIL**. Test A and
the Test C diagnostic passed, but Test B's frozen raw trace/acos rotation error
was `0.000135517229130207` rad, above the
`1e-4` rad gate. Therefore `PCL_BACKEND_IMPLEMENTATION_VALID=false` and
`PCL_BACKEND_PHASE_A_QUALIFICATION_AUTHORIZED=false`. No test was rerun after
the failure.

## v1 fixture rank and reclassification

The preserved v1 fixture has coordinate rank 2. With the normals estimated by
the unchanged PCL KSearch=50 implementation, its point-to-plane Jacobian/Hessian
rank is 3; sorted Hessian eigenvalues are
`[0.0, 0.0, 0.0, 3.359999963045121, 3.359999963045123, 64.0]`. The three zero modes correspond to
in-plane translations and rotation about the plane normal. The fixture cannot
observe all six rigid-body degrees of freedom and therefore was not a valid
hard qualification gate. Its historical smoke result remains FAIL; it is
reclassified as fixture-degenerate and backend qualification remains
NOT_EVALUATED, never rewritten as PASS.

## v2 nondegenerate fixture and Hessian

The seed-free fixture contains 806 finite unique points
from three perpendicular planes and an off-centre cuboid bump. Coordinate rank
is 3. The constructive analytic Hessian rank is 6 with
eigenvalues `[126.96221040873503, 131.15107985614438, 136.67100767861896,
230.31747283225394, 289.94028524243305, 328.8629856151476]`. Using the actual
PCL-estimated target normals, Test A also has rank
6 and eigenvalues
`[118.01923246777201, 119.47448076977795, 124.16784961960747, 230.02167799584092, 294.94216489723243, 306.6338104993603]`.

## Source and target normal statistics

For Test A, both source and target have finite=806,
zero=0, NaN=0, norm
min/median/max=`0.9999998987129718` / `1.0` /
`1.0000000884329288`, and direction rank
3. Test B source has finite=
806, zero=0, NaN=
0, norm min/median/max=
`0.999999885959997` / `0.9999999987336934` /
`1.0000001070329354`; its target statistics equal Test A target.
All Test C normals are finite unit normals with direction rank 1. The complete
per-test table is `tables/normal_statistics.csv`.

## Test A — NONDEGENERATE_IDENTITY

PASS. Raw convergence=true, finite transform=
true, finite fitness=
true, correspondences=806.
Final transform:

```text
1 1.76589562417e-10 1.39284705991e-09 8.08324851498e-10
-1.76589562417e-10 1 -4.57249932362e-10 -7.49585227222e-10
-1.39284705991e-09 4.57249932362e-10 1 -9.71347335899e-10
0 0 0 1
```

Translation update=`1.4692796979076661e-09` m; rotation update=
`0.0` rad.

## Test B — KNOWN_SMALL_TRANSFORM

FAIL. The source was constructed from the target with translation
`[0.01, -0.02, 0.03]` m and RPY `[0.2, -0.3, 0.5]` degrees. The expected
source-to-target transform is:

```text
0.999948215834 0.00872641587718 0.00523596383142 -0.00998203275573
-0.00874475856196 0.99995567146 0.00349060356624 0.0199818429078
-0.0052052712704 -0.00353621004779 0.999980199989 -0.0300180774879
0 0 0 1
```

The estimate is:

```text
0.999948203564 0.00872641336173 0.0052359639667 -0.00998203456402
-0.00874475482851 0.999955713749 0.00349060446024 0.0199818424881
-0.00520527129993 -0.00353621062823 0.999980151653 -0.0300180725753
0 0 0 1
```

Translation error=`5.251625720499032e-09` m (PASS).
Frozen raw rotation error=`0.0001355172291302067` rad
(FAIL versus `1e-4`). Raw convergence and transform/fitness finiteness are true.
The CLI's `qualification_pass=true` is intentionally a truth-free internal
health predicate; the authoritative Test B result is the verifier's
`microtest_pass=false`, because truth is never passed to the registration CLI.

The estimated 3x3 block has Frobenius orthogonality error
`1.3075527226247165e-07`. A post-result
closest-SO(3) projection gives diagnostic error
`0.0` rad, but the
protocol did not prospectively specify projection. This observation is not
used to change the gate, rerun the test, or rescue v2.

## Test C — PLANAR_DEGENERACY_DIAGNOSTIC

PASS as a diagnostic: point-cloud rank=2, Jacobian rank=
3, rank-deficient=
true, condition=`RANK_DEFICIENT`. Raw
PCL convergence was true but was not a gate;
the final transform was non-finite and is separately recorded.

## Scope and compliance

Phase A and Phase B were not run. No Development, Confirmatory, or old Test
seed was accessed; no RNG was used by the fixture generator. The frozen PCL
parameters and PCL 1.15.1 were unchanged. v1 reports and fixtures, Open3D, and
Native were not modified. No third backend, parameter rescue, commit rewrite,
or push was performed. This stopped v2 result authorizes no Phase A execution.
