# Zero-Perturbation Independent Backend Qualification Protocol v1

Status: prospectively frozen before PCL implementation, dependency-specific
parameter choices, and qualification trials. This audit can authorize only the
design of a future Open3D + PCL Development protocol. It cannot authorize a
full Development run, Confirmatory work, real-data validation, or a paper
claim.

## The prior Native result is excluded, not repaired

The frozen Development decision at commit
`ccbea9d91de287f0638cb5792f6a2405f312ff06` records Native full-reassociation
IDEAL_MATCHED q95 translation error of 0.205393106 m and 22 failures among 42
smoke trials. Therefore `NATIVE_BACKEND_QUALIFICATION_PASS` and
`NATIVE_BACKEND_FORMAL_MEASUREMENT_USE_AUTHORIZED` are permanently false for
this route. Native registration code, plane fitting, neighborhoods, residuals,
and solver behavior must not be changed, and Native must not be invoked in a
formal qualification trial.

The only candidate formal backends are the already frozen Open3D
point-to-plane implementation and a new PCL
`IterativeClosestPointWithNormals` implementation. Neither backend is truth;
qualification asks only whether exact reference initialization remains an
adequate fixed point under the frozen control.

## Immutable geometry, seeds, conditions, and inputs

The Development seed schedule, scene generator, scene dimensions, 0.10 m point
spacing, reference pose, end-face proportions, repeated-rib parameters, and
six existing condition definitions remain unchanged. Only the Development
split may be read. Confirmatory seed instantiation and old capture-range Test
seed access are forbidden and counted before RNG construction.

Phase A uses IDEAL_MATCHED only. The target is the frozen deterministic map.
Eligible source rows are exact target rows in the inclusive 0.30--20.0 m
reference range. For each scene, geometry seed, Development measurement seed,
and repeat, a SHA-256-derived PCG64 permutation selects the first 25% of
eligible rows without replacement, with at least 1024 rows, and the selected
rows are restored to target canonical order. Thus measurement seed and repeat
can change only exact source-subset membership; they cannot change the map,
reference pose, geometry, noise, or dropout. Each scene must produce at least
10 unique source checksums or the audit stops.

Each snapshot is materialized once. Open3D and PCL receive identical source
coordinates, target coordinates, reference pose, maximum correspondence
distance, and snapshot identity. Their source, target, reference-pose, and
snapshot checksums are retained. Backend-specific normal estimation and
internal correspondences are the only intended differences. No backend may
read a scene label for parameter switching, theoretical weak direction,
offline error, GT optimization signal, or the other backend's result.

## Frozen backend contracts

Open3D remains version 0.19.0+b012259 with point-to-plane ICP, 0.50 m maximum
correspondence distance, target-normal hybrid search radius 0.40 m and `max_nn`
50, relative fitness/RMSE tolerances `1e-8`, and 50 iterations. These are the
previously frozen parameters and cannot change in this audit.

PCL uses `pcl::PointNormal`, `pcl::NormalEstimationOMP`, and KSearch with
`k=50` independently for both source and target. Registration uses
`pcl::IterativeClosestPointWithNormals` with explicit
`TransformationEstimationPointToPlaneLLS`, maximum correspondence distance
0.50 m, 50 iterations, transformation epsilon `1e-10`, Euclidean fitness
epsilon `1e-10`, reciprocal correspondences disabled, symmetric objective
disabled, and same-direction normals enforced. One parameter set applies to
all scenes. Parameters cannot be changed after observing a build smoke or
qualification result.

PCL is installed, if necessary, only in `degen-lio-pcl-backend`. The existing
`degen-lio-zprm-py311` environment and system Python are not modified. Failure
to establish the required PCL packages, compile the CLI, or pass the identical
cloud identity smoke terminates the audit; no third backend may substitute.

## Phase A qualification and stopping rule

Phase A contains seven scenes, three frozen Development geometry seeds, two
Development measurement seeds, five repeats, and IDEAL_MATCHED only: 210
snapshots and 420 trials, split equally between Open3D and PCL. Native receives
zero trials.

Each backend independently requires zero solver failures, zero non-finite
outputs, q95 translation update at most 0.001 m, q95 rotation update at most
0.01 degrees, every scene median translation update at most 0.001 m, and at
least 95% of trials at or below 0.001 m translation update. Input checksum
mismatch, inadequate source diversity, seed firewall access, GT leakage, or a
Native invocation also stops the audit. No failed backend may be rescued by
threshold, normal, correspondence, iteration, or scene-specific changes.

## Conditional Phase B signal smoke

Phase B runs only if both Phase A backends qualify. It uses three Development
geometry seeds, Development `measurement_0`, repeat zero, seven scenes, and
only INDEPENDENT_NOISE_FREE and FULL_NOISE: 42 snapshots and 84 Open3D/PCL
trials. Native and Frozen remain excluded.

The smoke checks three descriptive signals: seven-scene median-error Spearman
agreement reaches 0.50 in at least one condition; rich room is among the two
lowest-error scenes for both backends in at least one condition; and a frozen
weak scene is among the three highest-error scenes for both backends in at
least one condition, with at least one weak/rich median ratio of two. These are
engineering signals, not scientific or paper results.

Only dependency readiness, CLI build, both Phase A qualifications, diversity,
input pairing, and the complete Phase B signal conjunction may authorize
writing a redesigned Open3D + PCL Development protocol. Full Development
execution, Confirmatory lock/run, real-data work, and Measurement mainline
authorization remain false in all outcomes of this task.
