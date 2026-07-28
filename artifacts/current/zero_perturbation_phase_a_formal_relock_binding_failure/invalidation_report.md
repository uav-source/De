# Phase A Formal Re-Lock Missing-Binding Failure

## Decision

The attempted formal re-lock is invalidated. The current runner accepted a synthetic execution lock that omitted both `publisher_sha256` and `independent_verifier_sha256`. Therefore `FORMAL_LOCK_BINDING_ENFORCEMENT_PASS = false` and formal Stage-1 execution remains unauthorized.

## Reproduction evidence

- Baseline commit: `6d7883afc1ecc580fa740e981d63eea30364a2f4`
- Synthetic input SHA-256: `fbf624ab32360cc948b1f4c29b52183e5eba8749c1ea1ef15567442e131ba8ee`
- Observed result: accepted by the v1 execution-lock validator
- Missing bindings: `publisher_sha256`, `independent_verifier_sha256`

The v1 validator compared an aggregate implementation SHA and then checked whether component labels existed in the current implementation manifest. It did not require those component SHA values in the lock and did not compare lock-carried publisher or verifier values to the current manifest.

## Exposure inventory

- Formal execution lock published: no
- Stage-0 cache reads: 0
- Formal seed accesses: 0
- Backend executions: 0
- Trial results: 0
- Native executions: 0
- Scientific result exposure: 0

This artifact records the blocker only. It does not alter the Stage-0 cache, scientific protocol, trial schema, backend parameters, scenes, seeds, metrics, or gates.
