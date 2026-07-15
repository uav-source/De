# Patent 1 Claim-Support Matrix — 2026-07-21

## Summary

| Result | Count |
| --- | ---: |
| Suggested independent-chain features | 8 |
| `FULLY_SUPPORTED` | 6 |
| `PARTIALLY_SUPPORTED` | 2 |
| `UNSUPPORTED` | 0 |

“Supported” here means traceable to specification, frozen code, tests, and
available controlled artifacts. It does not convert synthetic validation into
a real FAST-LIO2, real-IMU, or real-data claim.

## Matrix

| ID | Core feature | Specification/formula | Code/test/artifact | Support | Independent-claim recommendation | Principal risk |
| --- | --- | --- | --- | --- | --- | --- |
| C01 | Receive scan, local-map correspondence, variance, and pose prior | Fully described | Synthetic interface and Stage 2C prior path; no real acquisition/association | `PARTIALLY_SUPPORTED` | Keep as an input interface, not as completed real LIO integration | Sufficiency risk if dewarping/real correspondence is asserted as implemented |
| C02 | Build residual and six-DoF Jacobian at the prior | F01/F02 disclosed | Exact Stage 2C code and direct tests | `FULLY_SUPPORTED` | Keep; disclose perturbation convention | Over-narrowing if limited to point-plane only |
| C03 | Build whitened, state-scaled six-dimensional information | F03–F05 disclosed | Variance detector exact; robust weighting exists only in updater | `FULLY_SUPPORTED` for variance-only core | Keep variance+D core; move robust detector kernel dependent | Conflating detector H and updater H |
| C04 | Schur-marginalize rotation | F06 exact | Direct code/property test and Stage 2A mechanism evidence | `FULLY_SUPPORTED` | Keep in independent chain | Literal Schur wording may be designed around by equivalent factorizations |
| C05 | Normalize spectrum and compute effective-rank ODI | F07–F11 disclosed | Implemented and Stage 2A detector passes | `FULLY_SUPPORTED` | Keep three-dimensional ODI; make N_eff/epsilon details dependent | Missing duplicate-count invariance test; epsilon floor disclosure |
| C06 | Extract primary weak translation axis | F12 exact | Minimum eigenvector, canonical sign, no-GT test, formal direction pass | `FULLY_SUPPORTED` | Keep | Alternatives may output a weak subspace rather than one axis |
| C07 | Judge reliability using eigengap and temporal continuity | Eigengap core; time continuity optional | Eigengap present but denominator differs; temporal continuity absent | `PARTIALLY_SUPPORTED` | Keep eigengap only after P0 correction; move temporal continuity dependent | Core formula mismatch and unimplemented temporal semantics |
| C08 | Separately output triggered, stable, and actionable states | F15 exact | Direct truth-table/no-GT tests and Stage 2A gates | `FULLY_SUPPORTED` | Keep three-state semantics | Do not pull unimplemented quality flags into the independent claim |

The detailed CSV records specification, formula, code, test, and artifact
support separately, together with design-around, over-narrowing, and
sufficiency risks.

## Drafting boundaries

- Do not include fixed values `0.05`, `0.5`, `0.02`, or
  `0.035199792993590634` as universal independent-claim limitations.
- Do not include temporal persistence in the independent claim until it exists
  and is tested.
- Do not claim quality flags or explicit fallback outputs as implemented.
- Do not claim drift reduction, future-risk prediction, FAST-LIO2 integration,
  real IMU propagation, real association, or complete Degen-LIO performance.
- Preserve the no-GT runtime boundary: annotated tunnel axes and GT pose are
  offline evaluation inputs only.
