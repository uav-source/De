# Directional Capture Range MVP — Day 1 Protocol Lock

## Status and scope

Day 1 builds an engineering smoke-test engine for the **Algorithm-Conditioned
Empirical Directional Capture Range**.  It does not establish a new Measurement
paper result, a real-data result, or a property intrinsic to an environment.
Every result is conditional on the frozen scan, local map, reference pose,
registration and correspondence configurations, robust kernel, and termination
condition.

The pre-existing scientific state is immutable:

```text
STAGE2_GATE = FAIL
TRANSITION = PIVOT
EVALUATION_BUG_CONFIRMED = false
PILOT_LABEL_INVALIDATED = true
REFERENCE_INSUFFICIENT = true
METHOD_NEGATIVE_CONFIRMED = false
MEASUREMENT_PLAN_STATUS = NEW_PREREGISTERED_REPLACEMENT_PILOT_REQUIRED
```

The complete final scientific-audit decision is copied verbatim into the Day 1
configuration.  In particular, the audit remains complete and its primary
conclusion remains `PILOT_LABEL_INVALIDATED`.  Day 1 does not reinterpret any
of these outcomes.

The following trees are protected and must not be overwritten, modified, or
deleted:

- `artifacts/current/measurement_real_validation_pilot/`
- `artifacts/current/measurement_pilot_scientific_audit/`
- `artifacts/history/`

Day 1 also leaves the ODI and AIS formulas, Schur translation information
matrix, eigengap definition, original Measurement Pilot thresholds, FAST-LIO2
state estimator, Kalman gain, covariance, map update, data association, and all
existing negative results unchanged.  It uses no vision, no second dataset,
and no restored weak-direction updater.

The machine-readable lock is
`configs/capture_range/day1_protocol.yaml`.  The loader in
`src/eval/directional_capture_contract.py` rejects duplicate YAML keys,
non-finite values, missing or extra values, scalar type changes, list reordering,
and any other semantic change.

## Measurement object

For one registration snapshot, freeze all of the following:

1. current scan;
2. local map;
3. reference pose;
4. registration configuration;
5. correspondence configuration;
6. robust kernel; and
7. termination condition.

The measurement asks whether that fixed registration algorithm returns near the
independent reference pose when initialized at specified directional offsets.
It must not be reported as an algorithm-independent scene or environment
attribute.  Translation and rotation are measured separately; Day 1 performs
no search in a mixed six-DoF direction space.

The reference pose may be used only to construct the initial perturbation and,
after registration has stopped, to score the final pose.  It may not drive
correspondence construction, robust weighting, optimization, or stopping, and
it may never replace a failed result.

## Frozen product-manifold perturbation convention

The task statement writes perturbations compactly using `T_ref Exp(·)`.  A
literal right multiplication by a generic SE(3) exponential would express its
translation in the body frame, which is not the audited repository convention.
For Day 1 the notation is therefore resolved explicitly as the repository's
SO(3) × R3 product-manifold box-plus:

\[
R' = R\,\operatorname{Exp}(\delta\theta_{body}), \qquad
p' = p + \delta p_{world}.
\]

The mathematical perturbation-vector order used by the new Python code is

```text
[delta_theta_body, delta_position_world]
```

This is a right perturbation for SO(3) and an additive world-frame perturbation
for position.  It must not be described or implemented as one generic left or
right SE(3) update.

For a translation direction \(u_t\in S^2\) and nonnegative amplitude \(d\) in
meters:

\[
R_0=R_{ref},\qquad p_0=p_{ref}+d\,u_{t,world}.
\]

For a rotation direction \(u_r\in S^2\) and nonnegative amplitude \(\theta\)
in radians:

\[
R_0=R_{ref}\operatorname{Exp}(\theta u_{r,body}),\qquad p_0=p_{ref}.
\]

Thus the task's translation exponential is an intent-level shorthand for a
world-additive translation, while its rotation exponential agrees with the
repository's right-SO(3) update.

## Frozen Day 1 grid

Translation uses the six world-frame directions `+x`, `-x`, `+y`, `-y`, `+z`,
and `-z`, with amplitudes

```text
0.00, 0.02, 0.05, 0.10, 0.20 meter
```

Rotation uses the six body-frame directions `+roll`, `-roll`, `+pitch`,
`-pitch`, `+yaw`, and `-yaw`, with amplitudes

```text
0.0, 0.5, 1.0, 2.0, 5.0 degree
```

Degrees are only the human-readable configured grid.  Trial amplitudes and all
stored rotation quantities use radians: `0.0`, `0.008726646259971648`,
`0.017453292519943295`, `0.03490658503988659`, and
`0.08726646259971647`.

Each direction-amplitude cell has exactly three repeats.  YAML direction entries
show the signed physical vector and the amplitude grid is nonnegative.  The
runtime `PerturbationSpec` canonicalizes the basis vector and stores the sign
once in `signed_amplitude`, while retaining explicit `direction_id` and
`signed_side` fields (including at zero amplitude).  Positive and negative
sides must never be automatically merged or symmetrized.  Translation and
rotation groups also remain separate.

## Recovery success

Score the final pose against the independent reference pose using translation
error and SO(3) geodesic rotation error.  The frozen thresholds are:

```text
translation_error_threshold_m = 0.02
rotation_geodesic_error_threshold_deg = 0.5
rotation_geodesic_error_threshold_rad = 0.008726646259971648
```

A trial succeeds if and only if all of the following hold:

\[
\begin{aligned}
success={}&(e_t\le 0.02)\ \land\\
          &(e_R\le \pi/360)\ \land\\
          &solver\_converged\ \land\\
          &finite\_result\ \land\\
          &iteration\_limit\_not\_failed.
\end{aligned}
\]

Final cost or residual alone is never sufficient.  The thresholds are
preregistered and may not be tuned from Day 1 results.

## Recovery probability and Wilson interval

For fixed snapshot, perturbation type, signed direction, and amplitude, let
\(k\) of \(n\) trials succeed.  The empirical recovery probability is

\[
P_{rec}(d,u)=\hat p=\frac{k}{n}.
\]

Report the two-sided 95% Wilson score interval.  With the standard-normal
95% quantile \(z\), its center and half-width are

\[
c=\frac{\hat p+z^2/(2n)}{1+z^2/n},\qquad
h=\frac{z}{1+z^2/n}
\sqrt{\frac{\hat p(1-\hat p)}{n}+\frac{z^2}{4n^2}},
\]

and the saved interval is \([c-h,c+h]\), bounded to \([0,1]\).  An empty
group is invalid rather than an invented probability.

## Nonmonotonic curves and capture radii

Raw probability at every sampled amplitude is immutable evidence and must
always be saved.  Because finite-trial results may be nonmonotonic, also fit a
nonincreasing isotonic regression, weighted by each amplitude's trial count.
Save raw and fitted values side by side.  The fit must not overwrite, suppress,
or otherwise hide a raw reversal.

For a target probability \(q\), define the sampled-grid capture radius as the
smallest sampled amplitude whose fitted probability is at most \(q\):

\[
d_q(u)=\min\{d_i:\widehat P_{iso}(d_i,u)\le q\}.
\]

The two locked outputs are:

- `d50(u)`: \(q=0.5\);
- `d90(u)`: \(q=0.9\).

There is no interpolation in Day 1.  If no sampled amplitude reaches or falls
below the target, save the radius as null and set its `right_censored` flag to
true.  No extrapolated radius may be fabricated.  Right-censoring is evaluated
separately for `d50` and `d90` and separately for every signed direction.

## Formal and comparison registration paths

The formal path is full reassociation.  Starting from every perturbed initial
pose, every nonlinear iteration must re-run:

1. scan transformation;
2. nearest-neighbor search;
3. correspondence construction;
4. local plane fitting;
5. residual construction;
6. Jacobian construction;
7. robust weighting;
8. optimization update; and
9. termination evaluation.

The runtime evidence must show at least one full reassociation.  Initial and
final correspondence counts, a correspondence checksum, initial and final
costs, iteration count, and termination reason are recorded.  Correspondences,
planes, or Jacobians from the reference pose may not be reused in this path.

The frozen-Jacobian comparison may freeze `J`, `r`, `H`, and `b` at the
reference pose.  It is always marked `full_reassociation=false` and
`baseline_only=true`; it is isolated from formal capture-radius results.

The executable Day 1 registration settings are frozen in the YAML:

```text
max_iterations = 20
k_neighbors = 5
max_neighbor_distance_m = 0.75
plane_fit_tolerance_m = 0.05
huber_delta_m = 0.05
damping = 1e-6
rotation_step_tolerance_rad = 1e-5
translation_step_tolerance_m = 1e-5
min_correspondences = 30
```

These are new, algorithm-conditioned smoke settings.  They are not represented
as inherited FAST-LIO2 settings.

## Randomness and ground-truth boundary

The global seed is `15001`.  A trial seed is derived only from `snapshot_id`,
perturbation type, direction ID, signed amplitude, repeat index, and the global
seed.  A method name is never a seed component.  Day 1 defaults to no point
subsampling and zero injected range noise; correspondence ties use stable index
order.  Any future controlled random source requires a protocol revision and
must enter both the manifest and its checksum.

`ground_truth_weak_direction`, `pose_gt`, and `axis_gt` are forbidden optimizer
inputs.  A synthetic generator's theoretical weak direction may be consumed
only by a post-registration offline evaluator.  The required optimizer
ground-truth access count is zero.  Deleting or permuting offline ground-truth
metadata must not alter registration results.

## Smoke scope and Day 1 gate

The three small scenes are `geometry_rich_box`, `parallel_walls`, and
`long_corridor`.  The smoke expectations are limited to engineering evidence:
mostly successful small perturbations in the rich box, a visible trend of
weaker corridor-axis recovery than transverse recovery, both registration
paths running, complete output files, and zero forbidden optimizer access.
Smoke observations cannot change this protocol.

Day 2 is authorized only if all eight frozen gate fields are true:

```text
ENGINEERING_PASS
PROTOCOL_LOCKED
FULL_REASSOCIATION_VERIFIED
FROZEN_JACOBIAN_BASELINE_ISOLATED
NO_GT_LEAKAGE
SEED_DETERMINISM_PASS
SMOKE_PIPELINE_PASS
WORKTREE_CLEAN
```

Protocol lock alone never authorizes Day 2.  Day 1 does not assess novelty,
real-data effectiveness, superiority to covariance or other registration
methods, or completion of a new Measurement paper.
