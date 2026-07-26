# Directional Capture Range Day 1 Smoke Report

Run: `capture_range_day1_smoke`

This is an engineering smoke test of the Algorithm-Conditioned Empirical
Directional Capture Range engine.  It does not establish an algorithm-independent
property of a scene and does not complete a new Measurement paper.

## Frozen prior state

- STAGE2_GATE: FAIL
- TRANSITION: PIVOT

## Smoke scenes

- geometry_rich_box formal success rate: 1.000000
- geometry_rich_box small-perturbation success rate: 1.000000
- parallel_walls formal success rate: 0.666667
- long_corridor formal success rate: 0.900000
- long_corridor axial translation success rate: 0.000000
- long_corridor transverse translation success rate: 1.000000
- long_corridor axial-weaker trend visible: true

## Engineering gate

- ENGINEERING_PASS: true
- PROTOCOL_LOCKED: true
- FULL_REASSOCIATION_VERIFIED: true
- FROZEN_JACOBIAN_BASELINE_ISOLATED: true
- NO_GT_LEAKAGE: true
- SEED_DETERMINISM_PASS: true
- SMOKE_PIPELINE_PASS: true
- WORKTREE_CLEAN: true

- DAY1_ENGINEERING_GATE: PASS
- DAY2_AUTHORIZED: true
- optimizer GT access count: 0
- seed derivation mismatch count: 0
- deterministic output mismatch count: 0
- GT-result mismatch count: 0

No ODI formula, FAST-LIO2 estimator, second dataset, or visual input was modified or used.
