# Phase A Monolithic Lock Architecture Invalidation

This artifact preserves the failed Phase A v1.x monolithic-lock result at commit
`184fb9d1f00803c84d10d906846313626a7fb7fc`. It does not amend, replace, or
reinterpret any legacy lock or decision artifact.

The legacy Phase A v1.2 protocol lock combined immutable scientific provenance
with execution-implementation SHA bindings. Its frozen `stage1_engine` and
`stage1_runner` SHA values no longer match the separately requalified execution
chain. The resulting formal dry-run rejection occurred before Stage-0 cache
access and before any backend trial.

- `LEGACY_PROTOCOL_LOCK_SCIENCE_IMPLEMENTATION_COUPLED = true`
- `FORMAL_BACKEND_EXECUTION_COUNT = 0`
- `FORMAL_TRIAL_RESULT_COUNT = 0`
- `SCIENTIFIC_RESULT_EXPOSURE_COUNT = 0`
- `PHASE_A_STAGE1_BACKEND_RUN_AUTHORIZED = false`

The correction route is a new layered lock architecture. The old protocol lock,
snapshot lock, formal lock, artifacts, and failure decisions remain unchanged.

