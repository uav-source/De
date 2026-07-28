# Directional Capture Range Anchor Validity Audit

Development-only zero-perturbation diagnostic audit. No Confirmatory Test or scientific Measurement claim is authorized.

## Final decision

ANCHOR_AUDIT_COMPLETE = true
ZERO_PERTURBATION_BASELINE_VALID = false
REFERENCE_POSE_NOT_REGISTRATION_FIXED_POINT = true
NOISE_INDUCED_ANCHOR_SHIFT_CONFIRMED = true
DROPOUT_INDUCED_ANCHOR_SHIFT_CONFIRMED = false
GT_REFERENCE_ANCHOR_VALID = false
FULL_ZERO_SOLUTION_ANCHOR_VALID = false
NOISE_FREE_FULL_SOLUTION_ANCHOR_VALID = false
FROZEN_COMMON_ANCHOR_ELIGIBLE_FRACTION = 0.6952380952380952
D50_ZERO_ROOT_CAUSE_IDENTIFIED = true
FULL_REASSOCIATION_NONLINEAR_EFFECT_CANDIDATE = true
DIRECTIONAL_CAPTURE_RANGE_ROUTE_RECOVERABLE = false
NEW_CONFIRMATORY_PROTOCOL_AUTHORIZED = false
CONFIRMATORY_TEST_AUTHORIZED = false
NO_TEST_SEED_ACCESS = true
NO_GT_LEAKAGE = true
RECOMMENDED_ANCHOR = NONE
NONLINEAR_EFFECT_CANDIDATE_COUNT = 20
DIFFERENCES_REMAINING_AFTER_ANCHOR_MISMATCH_EXCLUSION = 24

## Formal zero success by scene and method

| scene | method | success | median translation (m) | q95 translation (m) | median rotation (rad) | q95 rotation (rad) |
|---|---|---:|---:|---:|---:|---:|
| END_FACE_TRANSITION_ABSENT | full_reassociation | 1/30 (0.033333) | 0.0400887722 | 0.129850493 | 0.000106957099 | 0.000142822117 |
| END_FACE_TRANSITION_ABSENT | frozen_jacobian | 13/30 (0.433333) | 0.0207918916 | 0.0396958208 | 8.81577745e-05 | 0.000214843216 |
| END_FACE_TRANSITION_PRESENT | full_reassociation | 30/30 (1.000000) | 0.00484940606 | 0.0138890579 | 0.00012956437 | 0.000157972087 |
| END_FACE_TRANSITION_PRESENT | frozen_jacobian | 30/30 (1.000000) | 0.00411592106 | 0.00464624687 | 0.000169073901 | 0.000367731991 |
| END_FACE_TRANSITION_WEAK | full_reassociation | 0/30 (0.000000) | 0.0125652972 | 0.042223154 | 0.000161031685 | 0.000446727308 |
| END_FACE_TRANSITION_WEAK | frozen_jacobian | 29/30 (0.966667) | 0.0138416975 | 0.019618956 | 0.000249199027 | 0.000536364246 |
| GEOMETRY_RICH_ROOM | full_reassociation | 30/30 (1.000000) | 0.000608153052 | 0.000770550492 | 9.28863211e-05 | 0.000104568205 |
| GEOMETRY_RICH_ROOM | frozen_jacobian | 30/30 (1.000000) | 0.000611674781 | 0.000776750087 | 9.02129287e-05 | 0.000106312754 |
| LONG_CORRIDOR | full_reassociation | 3/30 (0.100000) | 0.119694889 | 0.200129192 | 0.000101342698 | 0.000749694334 |
| LONG_CORRIDOR | frozen_jacobian | 0/30 (0.000000) | 0.111801177 | 0.134002343 | 0.000110584097 | 0.000583262886 |
| PARALLEL_WALLS | full_reassociation | 0/30 (0.000000) | 0.0644646622 | 0.170414029 | 0.000132165852 | 0.000292698435 |
| PARALLEL_WALLS | frozen_jacobian | 10/30 (0.333333) | 0.0340844242 | 0.0778644149 | 5.09451861e-05 | 0.000237673884 |
| REPEATED_STRUCTURE | full_reassociation | 30/30 (1.000000) | 0.00487938222 | 0.00650594759 | 0.000339904378 | 0.000487210032 |
| REPEATED_STRUCTURE | frozen_jacobian | 30/30 (1.000000) | 0.00312626268 | 0.00511472422 | 0.000361809521 | 0.000457624134 |

## Four-condition noise ablation

| condition | method | zero success | median translation (m) | median rotation (rad) | median cost change |
|---|---|---:|---:|---:|---:|
| NOISE_FREE | full_reassociation | 0.380952 | 0.0136540698 | 0.000111993956 | -0.00211937493 |
| NOISE_FREE | frozen_jacobian | 0.714286 | 0.0111161309 | 0.000146673654 | -0.0132979374 |
| SCAN_NOISE_ONLY | full_reassociation | 0.438095 | 0.0138499927 | 0.000101448995 | 0.00583289525 |
| SCAN_NOISE_ONLY | frozen_jacobian | 0.685714 | 0.00830249007 | 0.000126854547 | -0.0161653662 |
| MAP_NOISE_ONLY | full_reassociation | 0.414286 | 0.0151900286 | 0.000111272614 | 0.01040847 |
| MAP_NOISE_ONLY | frozen_jacobian | 0.714286 | 0.00548883598 | 0.000106639072 | -0.0115844031 |
| LOCKED_FULL_NOISE | full_reassociation | 0.447619 | 0.0122679181 | 0.000110235188 | 0.000924421794 |
| LOCKED_FULL_NOISE | frozen_jacobian | 0.676190 | 0.00684442966 | 0.000115915305 | -0.0163211287 |

## Reference fixed-point summary

| method | median gradient | q95 gradient | median first-step translation (m) | q95 first-step translation (m) | not-fixed fraction |
|---|---:|---:|---:|---:|---:|
| full_reassociation | 21.0342773 | 62.8929821 | 0.00619016983 | 0.100442162 | 1.000000 |
| frozen_jacobian | 21.0342773 | 62.8929821 | 0.00619016983 | 0.100442162 | 1.000000 |

The noise-induced status is based on matched-snapshot threshold crossings: NOISE_FREE success to SCAN_NOISE_ONLY failure = 0.095238; NOISE_FREE success to MAP_NOISE_ONLY failure = 0.100000. Aggregate full-reassociation success rates were NOISE_FREE = 0.380952, SCAN_NOISE_ONLY = 0.438095, and MAP_NOISE_ONLY = 0.414286; therefore the confirmation does not assert an aggregate success-rate degradation or a dominant noise mechanism.

Dropout causality is not identifiable from the frozen four contrasts because LOCKED_FULL_NOISE changes scan noise, map noise, and dropout together. The audit therefore does not claim a dropout-induced shift.

## Anchor candidates

| candidate | zero success | GT accurate | full self-consistent | frozen consistent | eligible | valid |
|---|---:|---:|---:|---:|---:|---:|
| GT_REFERENCE_ANCHOR | 0.447619 | 1.000000 | 0.447619 | 0.676190 | 0.447619 | False |
| FULL_ZERO_SOLUTION_ANCHOR | 0.466667 | 0.638095 | 0.466667 | 0.695238 | 0.447619 | False |
| NOISE_FREE_FULL_SOLUTION_ANCHOR | 0.476190 | 0.523810 | 0.476190 | 0.619048 | 0.380952 | False |

d50=0 primary root-cause counts: `{"MULTIPLE_ATTRACTORS": 612, "SUCCESS_THRESHOLD_CONFLICT": 288, "ZERO_SOLVER_FAILURE": 467}`.
Original full-vs-frozen mechanism counts: `{"anchor_mismatch": 8, "correspondence_switch": 32, "solver_failure": 28, "unexplained": 0}`.

All original Development outputs remained read-only. Success thresholds, amplitudes, directions, d50/d90, isotonic rules, geometry, ODI, FAST-LIO2, and vision inputs were unchanged.
