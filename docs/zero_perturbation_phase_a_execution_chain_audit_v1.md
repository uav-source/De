# Zero-Perturbation Phase A Execution-Chain Audit v1

This protocol is a concentrated engineering audit, not a scientific experiment.
It permanently invalidates the existing Phase A v1.2 Stage-1 execution
authorization because the frozen raw-result contract is incomplete.

The audit verifies one versioned result schema end to end: backend adapter,
strict validator, atomic writer, strict resume, analyzer, independent verifier,
publisher, artifact verifier, and SHA inventory. It runs exactly six trials from
three deterministic fixture-only snapshots through Open3D and PCL.

The formal Stage-0 cache at
`data/zero_perturbation/backend_phase_a_v1_2_stage0/` is forbidden input. The
audit must not list that directory, read its arrays, invoke a formal scene
generator or seed, execute a formal Phase A trial, invoke Native, or expose a
scientific result.

## Result contract

Every completed trial is a strict `phase_a_trial_result_v1` JSON document.
Unknown top-level fields, missing fields, backend-diagnostic mismatches,
non-finite numbers, and the legacy aliases `solver_failed`,
`failure_classifications`, `cli_exit_code`, and Open3D
`correspondence_count` are rejected. Writers validate before canonical,
atomic persistence. Resume validates the full result and its manifest SHA; it
never repairs or overwrites an invalid existing result.

Infrastructure attempt events are separate NDJSON records and never count as
completed trial results. The analyzer cannot repair raw results. The verifier
re-reads them from disk and independently recomputes inventories, updates,
rotation quality, quantiles, runtime summaries, failures, and the audit
decision. Publication is refused unless the independent result matches.

## Fixtures

The fixtures are deterministic and contain no random seed:

1. `FIXTURE_IDENTITY`: asymmetric, full-rank 3D cloud, identical source and
   target, identity reference.
2. `FIXTURE_NONIDENTITY_REFERENCE`: the same class of cloud with a fixed legal
   source-to-target SE(3) reference used as the exact initial transform.
3. `FIXTURE_NO_CORRESPONDENCE`: source and target are separated beyond the
   frozen 0.5 m correspondence distance and must produce a valid failure result.

Fixture observations validate only the execution chain. They do not evaluate
scene effects, qualify a backend, support a scientific conclusion, or mix with
formal Phase A data.

## Authorization ceiling

Passing every engineering gate with zero formal-cache, formal-seed, formal
backend, formal-result, and Native counts may authorize only a future Stage-1
relock. It does not authorize Stage-1 execution, Phase B, full Development,
Confirmatory, real data, or the Measurement paper mainline.
