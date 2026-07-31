# Synthetic Confirmatory v3 Bootstrap Contract Invalidation

## Decision

The old Synthetic Confirmatory v3 pre-run freeze is invalid for formal startup. The route is invalidated by a true implementation defect with frozen failure code `FORMAL_ROOT_EXISTENCE_MISCLASSIFIED_AS_RESUME`.

This is not a scientific failure. No v3 seed was accessed, no random generator was instantiated, no snapshot was constructed, no backend trial was executed, and no scientific result was produced. The v3 protocol, H1-H6, frozen models, backend bindings, plans, and seed values remain scientifically valid and unchanged. The same v3 seed set remains authorized for reuse after bootstrap repair qualification.

## Frozen identities

- Old branch: `feature/zero-perturbation-synthetic-confirmatory-v3-prerun`
- Old commit: `38d3dcddd818eb9ae243f73837d863f52bd1e233`
- Old tag: `archive/zero-perturbation-synthetic-confirmatory-v3-pre-run-pass`
- Old tag object: `3f7543dbb6499ea8d75132509c1559ddc64990e5`
- Old bundle: `/tmp/zero-perturbation-synthetic-confirmatory-v3-pre-run.bundle`
- Old bundle SHA-256: `c78dcc8b9177256b1ed11dfe4e9dcfd24a1f586035e211e3514ba63d7ba246f7`
- Failure tag: `archive/zero-perturbation-synthetic-confirmatory-v3-bootstrap-contract-fail`
- Failure tag object: `91d32974b20d96363b80ed8a3b74640c6fb35a28`
- Failure bundle: `/tmp/zero-perturbation-synthetic-confirmatory-v3-bootstrap-contract-fail.bundle`
- Failure bundle SHA-256: `754c0492ea3feceeb8547470b78cd3162ad957fa88552c27434950686782f363`

Both annotated tags peel to the unchanged old commit. The old pre-run tag was preserved and was not moved.

## Deterministic contract conflict

The formal bootstrap contract requires `<formal_root>/formal_command.log` to be durably recorded before runner entry. Creating that file necessarily creates the formal runtime root. At the old commit, `synthetic_confirmatory_v3_runner.py` line 645 treated `FORMAL_RUNTIME_ROOT.exists()` as the resume predicate and passed that value to `write_once_immutable_run_lock` at lines 650-652. `runtime_lifecycle_io.py` lines 574-586 then required an existing valid immutable run lock whenever `resume` was true.

A fresh run cannot already contain that lock because the runner has not yet entered its lock-creation step. The old startup sequence therefore formed an unsatisfiable loop:

1. Preserve the required command log before runner entry.
2. Command-log creation makes the formal root exist.
3. Root existence is misclassified as resume.
4. Resume requires an immutable run lock.
5. A fresh run cannot have created that lock yet.

The defect is not an infrastructure interruption, seed problem, scientific failure, snapshot-builder failure, or Git-gate failure.

## Preserved boundaries

- `OLD_V3_PRERUN_FREEZE_VALID = false`
- `OLD_V3_PRERUN_TAG_MOVED = false`
- `OLD_V3_SCIENTIFIC_PROTOCOL_INVALIDATED = false`
- `CONFIRMATORY_V3_ROUTE_INVALIDATED_BY_TRUE_IMPLEMENTATION_DEFECT = true`
- `V3_SEED_SET_REUSE_AUTHORIZED = true`
- `CONFIRMATORY_V3_RUN_AUTHORIZED = false`
- `SYNTHETIC_CONFIRMATORY_V3_EXECUTED = false`
- `SYNTHETIC_CONFIRMATORY_V3_COMPLETE = false`
- `SYNTHETIC_CONFIRMATORY_V3_PASS = NOT_EVALUATED`

The formal runtime root `/home/lj/zero_perturbation_runtime/confirmatory/synthetic_confirmatory_v3` remained absent when this invalidation record was prepared. Formal execution is forbidden until a four-state bootstrap lifecycle is implemented, independently qualified, re-frozen, and bound to a new pre-run release tag.
