# Directional Capture Range Day 2 — Development Feasibility

## Status and authority

This is a new, independent exploratory Development protocol. It does not amend,
replace, or reinterpret the archived Day 2 v1.0 or v1.1 files. Those protocols
remain blocked by specification ambiguity and their scientific result remains
`NOT_EVALUATED`.

The machine-readable authority is
`configs/capture_range/day2_development_feasibility.yaml`. Its mandatory scope
flags are:

```text
protocol_type = exploratory_development
scientific_claim_authorized = false
confirmatory_test_seed_access = forbidden
formal_scientific_pass_fail_authorized = false
day3_authorization = forbidden
```

This stage may answer engineering feasibility and descriptive trend questions
only. It may not create `day2_test_lock.json`, search candidate Hessian pairs,
perform manual `VALID` review, alter the production Schur matrix path, run a
formal rich-room bootstrap Gate, aggregate confirmatory Test blocks, or authorize
Day 3.

## Parent preservation and archived block

The four v1.0/v1.1 source files are immutable and are byte-checked against the
SHA-256 values in the YAML. The Development runner does not parse a parent Test
split; parent files are used only for byte-integrity validation. The pre-run
state is archived at commit `aed8d28597b2a0bc97fe41b29dd763d5d814a023`
under tag `archive/directional-capture-range-day2-v1.1-blocked` with zero
Development runs, zero Test runs, and no consumed Development or Test seeds.

## Seed firewall

Only the Cartesian product of geometry seeds `1101, 1103, 1107`, measurement
seeds `2101, 2111`, and repeat indices `0..4` is executable. Confirmatory seed
sentinels are equality guards only. Every seed pair is checked before it can
enter canonical hashing, scene generation, or RNG construction. An unknown or
confirmatory seed raises immediately. Direction, amplitude, and method name are
absent from all point-cloud realization streams.

No confirmatory seed may be run, instantiated, previewed, or written to an
output inventory. The manifest records attempted and materialized seed access;
both confirmatory counts must remain zero for `NO_TEST_SEED_ACCESS=true`.

## Directed inventory and roles

Every scene runs exactly 18 physical directed vectors: `pos_x`, `neg_x`,
`pos_y`, `neg_y`, `pos_z`, `neg_z`, followed by the twelve normalized
icosahedron vectors `ico_00..ico_11` in YAML order. Antipodes remain distinct.
There are no runtime aliases or extra weak/strong declarations. Role metadata is
stored only in `direction_roles.csv` and cannot change the runtime inventory,
registration configuration, snapshot metadata, seed streams, or runner inputs.

Rich-room X/Y/Z axes are controls. In Long Corridor, Parallel Walls, End Face
Weak, End Face Absent, and Repeated Structure, X is weak and Y/Z are strong.
End Face Present uses X as a transition control and Y/Z as strong. Icosahedron
vectors are supplemental in every scene.

## Scene generation and canonical hashing

The seven variants use the v1.1 dimensions and surface semantics, made
executable here by freezing primitive IDs and order, the grid-index bounds,
phase conversion, quantization, deduplication, and sort order. Planar coordinates
are `min + phase + k*spacing`, clipped with the stated tolerance. Map and scan
use independent phase roles. Repeated ribs share one longitudinal phase and are
attached to both side walls. The weak end face uses a canonical per-point hash
threshold. Map and scan use a 20 m Euclidean range around the reference position;
scan points are then transformed into the reference sensor frame. This remains
a 360-degree, no-occlusion synthetic model.

Canonical structured hashes use UTF-8 JSON, sorted keys, separators `(',',
':')`, float values converted with `float.hex()`, and SHA-256. Negative zero is
normalized to positive zero. Hash-to-seed uses the first 16 digest bytes as an
unsigned big-endian integer; hash-to-unit-interval uses the first eight bytes
divided by `2^64`. Array hashes encode dtype, shape, and C-order values through
the same canonical representation. This canonical rule applies to new
Development seeds, scenes, snapshots, and outputs; it does not change the
production correspondence-checksum implementation. Cross-process equality is a
required test.

## Base snapshots and noise

A base snapshot is exactly:

```text
scene variant + geometry seed + measurement seed + repeat index
```

It is generated once and contains one noisy scan, one noisy map, and one dropout
realization. NumPy `Generator(PCG64)` streams are keyed only by the base snapshot
identity and stream role. Dropout masks are generated first, then Gaussian noise
for every pre-dropout point, and finally masks are applied. Every direction,
amplitude, full-reassociation run, and frozen-Jacobian run for that base snapshot
reuses the same immutable scan/map object and the same four recorded checksums.
Any method, direction, or amplitude pairing mismatch is an Engineering failure.

## Registration, amplitudes, and success

The Day 1 point-to-plane registration configuration and pose convention are
unchanged. A fixed local-map KD-tree may be reused within a base snapshot, while
full reassociation still rebuilds transformed scan points, neighbors,
correspondences, planes, residuals, Jacobians, and robust weights at every
nonlinear evaluation. The frozen-Jacobian reference model is prepared once per
base snapshot and performs no trial-time reassociation.

Translation amplitudes are `0, 0.01, 0.02, 0.05, 0.10, 0.20, 0.40, 0.80 m`.
Rotation amplitudes are `0, 0.25, 0.50, 1, 2, 5, 10, 20 deg`. Success remains
translation error at most `0.02 m` and rotation geodesic error at most `0.5 deg`,
with convergence, finite output, and no iteration-limit failure also required.

The optimizer receives scan, map, initial pose, registration configuration, and
method-independent numerical seed only. Direction roles and theoretical weak
directions are offline analysis metadata and are never optimizer inputs.

## Curves, censoring, and descriptive comparisons

For each scene/geometry/measurement block, the five repeat snapshots form the
trials at each amplitude. Raw success probability and Wilson 95% bounds are
preserved. Raw curves alone drive full-vs-frozen maximum gaps, trapezoidal
integrals, and non-monotonicity audit. Weighted non-increasing isotonic curves
are used only for the discrete sampled-grid d50 and d90 definitions. There is no
interpolation or extrapolation.

Right-censored d50/d90 values remain null. If both X antipodes are censored, the
weak radius is censored, separation is null, and the block is not evaluable.
Development scene summaries include only evaluable blocks and impose no 4/6
Gate. A censored value is never replaced by zero, negative infinity, or the
maximum amplitude as an exact radius. A strong-radius denominator at or below
`1e-12` makes separation null and the block unevaluable with reason
`NONPOSITIVE_STRONG_RADIUS`; finite negative separation is retained, not clamped.

The X-axis trend is descriptive and predeclared for Long Corridor and Parallel
Walls using full-reassociation translation d50. The Development flag is true
only when both scenes have at least one evaluable block and positive median
separation; it is not a scientific Gate.

Full versus frozen comparison is limited to translation `pos_x` and `neg_x` in
End Face Weak, End Face Absent, and Repeated Structure. It reports raw maximum
probability gap, signed raw trapezoidal integral difference, exact d50 difference
only for two exact values, censoring pattern, and full-path correspondence
checksum transitions. It has no confirmatory threshold.

Both registration paths nevertheless execute the complete exploratory matrix:
210 base snapshots by 18 directions by eight amplitudes by two perturbation
families by two paths, for exactly 120,960 trial rows. “Limited” above constrains
the descriptive comparison table, not trial execution.

## Development repeatability

Every full-reassociation translation block/direction curve is bootstrapped 500
times with seed `161803`. A curve-specific PCG64 stream is canonically derived
from the bootstrap seed, block ID, and direction ID. Each replicate draws five
repeat indices with replacement once, shares that draw across all amplitudes,
and recomputes isotonic d50. Censored
bootstrap d50 values remain absent. Statistics report uncensored fraction,
finite mean, sample standard deviation with `ddof=1`, CV, eligibility, and reason.
If the finite mean is at most `1e-12`, CV is null with reason
`ZERO_MEAN_D50`. Fewer than two uncensored values also yields a null standard
deviation and CV. Eligibility additionally requires an uncensored fraction of
at least 0.80. Development repeatability has no formal Gate.

## Outputs and completion

The result and current-artifact directories must contain the exact fifteen files
listed in the YAML and must match byte-for-byte. `SHA256SUMS` hashes every other
file. CSVs use UTF-8, LF endings, fixed columns, and deterministic row order.

`CONFIRMATORY_PROTOCOL_READY=true` requires an executable pipeline, all seven
scenes, exactly 18 directions per scene, exact snapshot pairing, no confirmatory
seed access, no GT leakage, and no newly discovered ambiguity. Directional trend
and full-vs-frozen difference flags are reported but are not prerequisites.

No outcome from this Development stage is a final Day 2 scientific PASS/FAIL,
evidence of d50 novelty, or Day 3 authorization.
