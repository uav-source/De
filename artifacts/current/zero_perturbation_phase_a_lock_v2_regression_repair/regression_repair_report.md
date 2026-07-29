# Phase A Lock Architecture v2 — Repository Regression Compatibility Repair

## Decision

The limited repair did not satisfy every final gate and stopped without a third compatibility patch.

- Original audited failures: 2/2 PASS.
- New compatibility tests: 15/15 PASS from a clean committed worktree.
- v2 targeted tests: 27/27 PASS.
- Tamper rejection: 23/23 PASS before cache access.
- Formal dry-run: 210 snapshots / 420 trials; Open3D/PCL/Native = 210/210/0; seed/backend/result/STARTED = 0/0/0/0.
- PCL v3 CTest: 3/3 PASS.
- Full pytest: 1 failed, 1775 passed, 1 skipped, 262 warnings in 89.78s.
- Full-suite failure: `tests/test_phase_a_v2_active_runner_no_placeholder.py::test_active_runner_dry_run_reaches_complete_nonexecuting_plan` observed a transient dirty worktree during the full pytest session.
- Historical parser parse errors: 0.
- Historical result non-reduction: FAIL; the strict key policy removed prior resolved process-noise seed values, so the explicit non-reduction requirement is not proven.

## Frozen boundaries

Scientific, Snapshot, Implementation, and Formal Run Lock file SHA-256 values remain unchanged. The active runner, v2 engine, backends, scientific metrics, thresholds, and formal seed values were not modified. Existing v2 artifact `SHA256SUMS` verification passed, and the original v2 FAIL artifact remains byte unchanged.

No formal Phase A, formal backend, Phase B, Development, Confirmatory, or real-data run was performed. No push occurred.

`PHASE_A_LOCK_ARCHITECTURE_V2_REGRESSION_REPAIR_PASS = false`  
`PHASE_A_LOCK_ARCHITECTURE_V2_PASS = false`  
`PHASE_A_STAGE1_BACKEND_RUN_AUTHORIZED = false`  
`PHASE_A_STAGE1_BACKEND_EXECUTED = false`  
`DAY1_SCIENTIFIC_VALIDATION_PASS = NOT_EVALUATED`
