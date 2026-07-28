# Zero-Perturbation Phase A Stage-1 Formal Lock v1.1

This protocol corrects only Formal Execution Lock binding enforcement. It does not change the frozen Phase A v1.2 scenes, seeds, repeats, condition, backend parameters, result schema, metrics, thresholds, quantile method, failure definitions, or gates.

The lock uses `phase_a_formal_execution_lock_v1` and has exactly 20 required top-level fields. Unknown top-level fields, unknown implementation bindings, aliases, missing bindings, malformed SHA-256 values, and legacy locks are rejected. `implementation_bindings` contains exactly 14 SHA-256 values, including mandatory publisher and independent-verifier bindings.

Validation occurs before any Stage-0 snapshot cache read. The validator first validates the exact schema and payload hash, then validates the v1.2 protocol, Stage-0 snapshot lock, 210/420 trial plan, scientific contract, and every implementation binding against the newly frozen execution-chain audit v1.1 manifest. The runner may not infer or supplement a binding outside the lock.

The only permitted run in this correction round is a dry-run. It may verify the existence and SHA integrity of all 210 cached snapshots, but it must access no formal seed, execute no backend, write no trial result, emit no `STARTED` attempt event, and execute no Native implementation.

Formal Stage-1 backend execution can be authorized only after the strict lock tests, six-trial fixture execution-chain audit v1.1, independent artifact verification, scientific-contract zero-difference audit, strict formal-lock verification, dry-run, and tamper-rejection suite all pass. Authorization does not mean execution occurred; this round fixes `PHASE_A_STAGE1_BACKEND_EXECUTED = false` and `DAY1_SCIENTIFIC_VALIDATION_PASS = NOT_EVALUATED`.
