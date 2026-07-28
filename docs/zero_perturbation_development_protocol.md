# Zero-Perturbation Registration Measurement — Development Protocol v1

Status: prospectively frozen before any Development snapshot. This is an
engineering and feasibility study, not a confirmatory experiment or a paper
claim. Confirmatory execution, real-data validation, and Measurement-paper
authorization remain false.

## Measurement object

For a fixed scene, scan, local map, reference pose, backend, correspondence
policy, robust kernel, and stopping rule, registration starts exactly at the
reference pose. For output pose `T_estimated`, the rotation vector is
`Log(R_reference^T R_estimated)` and the world-frame translation vector is
`p_estimated - p_reference`. Their Euclidean norms are the single-trial
zero-initialization registration errors. The historical 0.02 m and 0.5 degree
capture-range thresholds are not used.

A systematic offset is defined only after grouping by scene variant, geometry
seed, condition, and backend and aggregating both measurement seeds and all
five repeats. Translation/rotation covariance uses `ddof=1`; repeatability RMS
is the square root of its trace. The systematic fraction is the norm of the
mean translation vector divided by the mean single-trial translation norm,
or null when that denominator is at most `1e-12`. A single trial is never
called a bias.

## Frozen inputs and seed firewall

Seeds are read from
`configs/zero_perturbation/seed_schedule_v1.json`; integer seeds are neither
hand-entered nor re-derived. Only the Development geometry, measurement,
bootstrap, and backend labels may be instantiated. Confirmatory seed
instantiation and access to old capture-range Test seeds are forbidden and
counted before any RNG construction. A method name never enters snapshot
randomness.

Seven already-audited scene variants and their exact geometry are copied into
`configs/zero_perturbation/development_v1.yaml`. The source scene configuration
and generator are SHA-256 locked. No scene dimension, spacing, reference pose,
end-face fraction, or repeated-rib parameter may change after results exist.

## Snapshot and conditions

A snapshot is `(scene, geometry seed, measurement seed, repeat, condition)`.
The six and only six conditions are IDEAL_MATCHED, INDEPENDENT_NOISE_FREE,
SCAN_NOISE_ONLY, MAP_NOISE_ONLY, DROPOUT_ONLY, and FULL_NOISE. One snapshot
materializes scan, map, noise, dropout masks, and reference pose exactly once;
native full reassociation, native frozen Jacobian, and Open3D point-to-plane
consume identical arrays and checksums. Development contains 1260 snapshots
and 3780 trials. The 42-snapshot smoke uses one geometry seed, one measurement
seed, one repeat, all scenes, all conditions, and all three methods.

IDEAL_MATCHED uses a deterministic map subset transformed exactly into the
sensor frame. The subset is exactly the map rows whose Euclidean range from
the reference translation is in the inclusive interval [0.30 m, 20.0 m], in
the map's canonical row order. Every other condition uses independent frozen
map/scan grid phases. Noise/dropout streams use PCG64 seeds derived from the
scheduled Development measurement seed plus scene, geometry seed, repeat,
condition, and stream role; method names are excluded. Masks are generated
before noise, noise is materialized for all pre-dropout rows, and masks are
then applied. Magnitudes are those in the locked YAML.

## Backends and reassociation

Native full reassociation rebuilds correspondences, local planes, residuals,
and Jacobians on every nonlinear evaluation. Native frozen fixes the initial
correspondences, planes, Jacobian, and linear model and is only a local-model
baseline, never truth. Correspondence turnover uses the Jaccard distance of
`(scan index, sorted neighbor-index tuple)` sets; accepted-index turnover and
common-index normal angle changes are also retained. Full/frozen pose
difference is `inverse(T_frozen) * T_full`.

Open3D 0.19.0+b012259 runs point-to-plane ICP with maximum correspondence
distance 0.50 m; target-map normals use radius 0.40 m and at most 50 neighbors;
relative fitness and RMSE tolerances are `1e-8` and maximum iterations are 50.
It receives the same points and exact reference initialization as native, but
does not receive native correspondences, scene-specific tuning, theory, or GT.

## Gates and stopping rule

IDEAL_MATCHED requires native full and Open3D q95 translation error at most
0.001 m, q95 rotation at most 0.01 degrees, and zero solver failures. Failure
stops the route without threshold or parameter changes.

Exploratory scene effect requires, in INDEPENDENT_NOISE_FREE or FULL_NOISE,
the same weak scene to reach at least twice rich-room median translation error
for both backends. Cross-backend signal requires scene-ranking Spearman rho at
least 0.50 in one of those conditions. Reassociation signal requires one of
the four frozen weak scenes to have at least three times rich-room median
full/frozen translation difference and absolute Spearman correlation at least
0.30 between correspondence turnover and that difference.

Only when engineering completeness, seed/GT firewalls, IDEAL_MATCHED, all
three preliminary signals, and the absence of new protocol ambiguity pass may
generation of a future Confirmatory lock be authorized. This Development task
does not generate that lock and never authorizes or runs Confirmatory.
