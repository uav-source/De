# Day 5 Remediation runtime-equivalence contract

This contract separates three questions in order: FAST-LIO2 baseline repeatability, in-call tap immutability, and compact-export scheduling equivalence. A failed prerequisite stops all later phases.

## Fixed scope

- Scientific state remains `STAGE2_GATE=FAIL` and `TRANSITION=PIVOT`.
- Runtime modes are the closed enum `AUDIT_ONLY`, `CAPTURE_ONLY`, and `COMPACT_EXPORT`.
- Day 5 remediation uses `DETECTOR_MINIMAL_V1`; `FULL_AUDIT_V1` remains covered for historical Day 3 behavior but is not selectable by the remediation runner.
- Runtime audit uses `HBRTAUD2` version 2. Observation export uses `HBROBSV3` version 3. Both are explicit little-endian streams with per-record FNV-1a-64 checksums and a record-count/file-checksum trailer.
- No background writer thread and no per-frame flush are allowed.
- Production detector execution is post-replay only.
- Position, rotation, and covariance equivalence tolerances remain `1e-12`.

## Frozen environment

- Build: `RelWithDebInfo`.
- FAST-LIO2 core: 0; rosbag core: 1.
- Playback: ROS simulated time, rate 0.25.
- BLAS/OpenMP thread environment: one thread, static scheduling.
- Publishing, runtime position logging, and PCD saving are disabled symmetrically.
- Only `avia_quick_shack` and `avia_outdoor_run_100hz` with their locked bag hashes and full fixed clips are allowed.

## Phase gates

1. Baseline: three `AUDIT_ONLY` runs per sequence, all three pairwise comparisons strictly identical.
2. Capture: only after baseline passes; ABBA `AUDIT_ONLY/CAPTURE_ONLY/CAPTURE_ONLY/AUDIT_ONLY`.
3. Export: only after capture passes; ABBA `AUDIT_ONLY/COMPACT_EXPORT/COMPACT_EXPORT/AUDIT_ONLY`.

The comparator exposes `runtime_equivalence_pass`, `final_map_equivalence_pass`, and `overall_equivalence_pass`; it has no ambiguous generic `pass`. First divergence uses the ordered enum `NONE`, `INPUT_GROUP`, `PRIOR_STATE`, `PRIOR_COVARIANCE`, `FORMAL_LINEARIZATION`, `POSTERIOR_STATE`, `POSTERIOR_COVARIANCE`, `MAP_SIZE`, `FINAL_MAP`.

If baseline fails, `FAILURE_CLASSIFICATION=BASELINE_RUNTIME_NONDETERMINISM`, later phases are not run, and Day 6 remains unauthorized.
