# Measurement Real Validation Pilot

## Scope and frozen boundary

This is a single-sequence Measurement pilot, not a complete Degen-LIO
experiment. `STAGE2_GATE=FAIL` and `TRANSITION=PIVOT` remain unchanged. The
interval lock was committed before detector execution, with SHA-256
`c74d3af08054979c2cf0ecbb086a7b218a6541f691b82a1eb20706047086e4b4`. No interval, metric definition, detector
threshold, or reference axis was changed after detector output became visible.

## Input and safety

- Dataset/sequence: MUN-FRL Lighthouse benchmarking bag
- Bag SHA-256: `562bafc57dab7fdac3d8959cf6836b3f4508c4fa60147b11d718552180543162`
- FAST-LIO2 frames: 1722
- Valid detector frames: 1719 (0.9983)
- Same-call tap mutation count: 0
- Detector feedback count: 0
- Frozen detector mismatch count: 0
- Reference input access count: 0
- FAST-LIO2 crash count: 0

The one export-boundary estimator-checksum change is reported separately as
`runtime_export_estimator_checksum_change_count=1`.
The same frame's tap pre/post state, covariance, Jacobian, innovation,
correspondence, and map-size checksums are identical; it is not counted as a
same-call tap mutation.

## Position-only reference

`/fix` was converted from WGS84 to ENU using the first valid RTK fix. The
reference is position-only and has no reference orientation. FAST-LIO2 and ENU
positions were aligned offline with rigid SE(3) Kabsch alignment and unit scale.
Position ATE RMSE is 0.3580 m; median local
5 s translation error is 0.1264 m.

## Weak direction and eigengap

The structural-interval median angle error is 30.706 deg
(q75 32.029, q95 34.259). Reliable-frame
median is 30.800 deg; unreliable-frame median is
28.980 deg. Therefore, the preregistered question
"are reliable frames actually more accurate?" evaluates to
`False`.

## ODI and conventional baselines

ODI AUROC is 0.0020; the best traditional metric is
`primary_eigengap_ratio` with AUROC
0.3661. The ODI-minus-best gap is
-0.3642.

`ODI_ADVANTAGE_ESTABLISHED=False`

## Gates

- Engineering Gate: `True`
- Runtime target Gate: `True`
- Scientific Pilot Gate: `False`
- `MEASUREMENT_REAL_PILOT_PASS=False`
- `SECOND_DATASET_EXPANSION_AUTHORIZED=False`

If the scientific gate fails, this stage stops here. No second dataset is
authorized, and no post-result interval, formula, threshold, or reference-axis
adjustment is permitted.
