# Directional Capture Range Anchor Validity Audit

This document describes a Development-only diagnostic audit of the archived
Day 2 Development result at commit
`2fa148870cae0ede632de3e1b5c192bb7e37b65d`. It does not amend the Day 2
capture-range protocol and does not authorize Confirmatory Test access.

## Immutable boundaries

- Only Development geometry seeds `1101`, `1103`, and `1107`, measurement
  seeds `2101` and `2111`, and repeats `0..4` are accepted by the inherited
  runtime firewall.
- Translation success remains `0.02 m`; rotation success remains `0.5 deg`.
- Directions, amplitudes, d50/d90, isotonic fitting, geometry, ODI,
  FAST-LIO2, and vision inputs are unchanged.
- The archived Development result and result artifact are read-only inputs.
- `CONFIRMATORY_TEST_AUTHORIZED` is fixed to `false`.

## Formal zero registration

Each of the 210 archived base snapshot identities is regenerated with the
locked full-noise realization. The scan, map, dropout, and base-snapshot
checksums must match the archived inventory before registration. Full
reassociation and frozen Jacobian are each run once from the exact reference
pose. A second identical run is used only for deterministic review. Both the
translation and rotation distance between final poses must be at most
`1e-10`.

The robust reference gradient is `J.T @ (w * r)` using the optimizer's frozen
Huber rule. A reference is diagnosed as not being a registration fixed point
when the gradient norm exceeds `1e-8`, the deterministic review passes, and
the stable final motion exceeds either optimizer step tolerance (`1e-5 m` or
`1e-5 rad`). This diagnostic is not interpreted as directional degeneracy.

## Frozen four-condition ablation

Exactly four conditions are evaluated: `NOISE_FREE`, `SCAN_NOISE_ONLY`,
`MAP_NOISE_ONLY`, and `LOCKED_FULL_NOISE`. No fifth condition is permitted.
The last condition must reproduce the archived Development checksums exactly.

A scan- or map-noise effect is confirmed only when an individually isolated
noise condition lowers full-method zero success by at least `0.05`, or moves
at least `0.05` of snapshots from successful under `NOISE_FREE` to failed.
Dropout is not causally identifiable from the four frozen contrasts because
`LOCKED_FULL_NOISE` changes scan noise, map noise, and dropout together. The
audit therefore keeps `DROPOUT_INDUCED_ANCHOR_SHIFT_CONFIRMED=false` and
records the confounding rather than adding a forbidden fifth condition.

## Anchor diagnostics

The three candidates are the GT reference, the locked-full-noise full zero
solution, and the noise-free full zero solution. Absolute accuracy uses the
unchanged `0.02 m` and `0.5 deg` limits. Across-repeat clusters are connected
components under the same pairwise translation and rotation limits. More than
one component in any five-repeat scene block is a multiple-attractor result.

The full-zero candidate is valid only when at least 95% of snapshots are
converged, finite, deterministic, and absolutely accurate, and no scene block
has multiple attractors. Frozen common-anchor distance eligibility uses the
same absolute limits and is reported even if the full-zero candidate is
globally invalid; in that case it cannot authorize subsequent comparison.

## Root-cause and mechanism diagnosis

Every original exact `d50=0` row receives one primary reason, using the
predeclared precedence in
`configs/capture_range/anchor_validity_audit.yaml`, plus optional secondary
reasons. The 32 original full-vs-frozen descriptive differences are checked
for correspondence switching, anchor mismatch, solver failure, clustering,
failure onset, linear frozen behavior, and low-residual wrong-pose outcomes.
A nonlinear-effect candidate requires no majority anchor mismatch, positive
full correspondence change, raw gap at least `0.8`, and repeat-level recovery
mismatch at least `0.8`.

Route recovery requires every gate in the audit YAML. Even a recoverable route
would authorize only preparation of a new confirmatory protocol; the retained
Test seeds remain inaccessible in this stage.
