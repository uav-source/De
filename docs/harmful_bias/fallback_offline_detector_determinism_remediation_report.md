# Fallback C Offline Remediation Report

Three fresh Python processes each consumed 487 frozen observations. Each
emitted 487 backward-compatible adapter records (486 valid and one
`TOO_FEW_CORRESPONDENCES`) and 487 valid direct-production diagnostic records.

The production-executed domain contains 486 records. Metric mismatch count is
0, with maximum absolute error 0.0.
The adapter-precondition domain contains record 284 / scan 287 with a 5x6
Jacobian. Its contract mismatch count is 0; its direct
production result is diagnostic and does not change adapter policy.

Adapter and direct streams match across all three processes by per-record
checksum, exact JSON line bytes, and whole-file SHA-256.
`PRODUCTION_DETECTOR_DETERMINISM_ON_DIRECT_STREAM_PASS=true`,
`ADAPTER_PIPELINE_DETERMINISM_PASS=true`, and `FALLBACK_C_PASS=true`.
`FULL_ADAPTER_PRODUCTION_CALL_COVERAGE_PASS=false` is the expected disclosed
state because one record remains in the adapter-precondition domain.

This work did not evaluate detector effectiveness or harmful-bias
detectability. No ROS, FAST-LIO2, bag, Development, Holdout, or Future Test
execution occurred. Day 6 remains unauthorized pending separate GPT audit,
and formal Degen-LIO remains incomplete.
