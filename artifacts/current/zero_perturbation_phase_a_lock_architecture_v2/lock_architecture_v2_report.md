# Phase A Lock Architecture v2 Decision

The monolithic v1.2 lock failure remains archived and unchanged. The v2 route
separates scientific protocol, byte-exact snapshot provenance, execution
implementation, and formal authorization into an acyclic three-edge graph.

- Legacy fields classified: 84/84 (unclassified 0, multiple 0)
- Classification counts: {"DOCUMENT_METADATA": 6, "EXECUTION_IMPLEMENTATION": 64, "FORMAL_RUN_AUTHORIZATION": 3, "LEGACY_DUPLICATE": 1, "SCIENTIFIC_PROTOCOL": 9, "SNAPSHOT_PROVENANCE": 1}
- Graph acyclic / duplicate bindings: True / 0
- Scientific implementation fields / projection differences: 0 / 0
- Snapshot inheritance: 210/210, original file SHA `a63f8ea07e9420f72c08cf1c16812ee058f5e2bfa0575a5e3d39f6bda2f21f8a`
- Fixture trials: 3 snapshots / 6 trials; fresh/resumed 6/6
- Resume skipped/reexecuted: 2/0
- Analysis/verifier differences: 0
- Fixture publication tables/figures: 10/5
- Implementation scientific fields / Formal duplicated fields: 0 / 0
- Layer tamper rejection: 23/23 before cache access
- Dry-run snapshots/trials: 210/420
- Dry-run Open3D/PCL/Native plan: 210/210/0
- Formal seed/backend/result/STARTED counts: 0/0/0/0
- PCL v3 CTest: 100% tests passed, 0 failed, 3/3
- Targeted pytest: 27 passed in 3.20s
- Full pytest: 2 failed, 1758 passed, 1 skipped, 262 warnings in 88.66s

Full-suite blockers requiring manual review:

1. `tests/test_backend_phase_a_runner_no_placeholder.py` rejects an existing
   conditional `RuntimeError` integrity guard in the legacy v1 runner. The v2
   scope does not authorize modifying that runner or the legacy test.
2. `tests/test_stage2_failure_day13_seed_exclusion.py` scans the new Scientific
   Lock and expects `geometry_seeds` to be integer scalars, while the frozen v2
   schema preserves each source seed's index/label/value object. Correcting this
   now would require changing a frozen lock schema or an out-of-scope historical
   seed scanner.

`PHASE_A_LOCK_ARCHITECTURE_V2_PASS = false`  
`PHASE_A_STAGE1_BACKEND_RUN_AUTHORIZED = false`  
`PHASE_A_STAGE1_BACKEND_EXECUTED = false`  
`DAY1_SCIENTIFIC_VALIDATION_PASS = NOT_EVALUATED`
