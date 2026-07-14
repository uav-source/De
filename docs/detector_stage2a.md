# Detector Consolidation Stage 2A

Stage 2A is a detector-only, independent confirmation. It evaluates two claims:

1. ODI increases with controlled geometry and observation degradation severity.
2. When the minimum information direction is identifiable, it aligns with the known weak axis.

It does not estimate drift magnitude, issue online risk warnings, run process-noise trials, implement a weak-subspace update, integrate FAST-LIO2, or constitute a complete LIO method.

## Semantics

The primary direction is always the eigenvector of the smallest translation-marginal information eigenvalue. Its stability is decided only by the normalized first eigengap. ODI threshold crossing is a separate detector state. A direction is actionable only when both states are true.

An empty threshold-defined weak subspace has `triggered=false`, dimension zero, projector `None`, and NaN alignment. NaN therefore means “no weak subspace was selected”, not “a selected subspace is perpendicular”.

## Controlled mechanisms

Geometry levels use deterministic additive measurement identities so that `L4 < L3 < L2 < L1` as strict sets. Shared points, normals, and noise are bitwise identical. Every information increment is audited as positive semidefinite to tolerance `1e-8`.

Observation levels use a fixed geometry and common candidate uniforms, producing nested retained axial sets from O1 through O4. Raw information is used for geometry-mechanism checks and effective-sample-size-normalized information for observation-mechanism checks.

## Split and lock

Development uses 13 geometry seeds and four sensor seeds for 468 sensor runs. The reserved test uses ten disjoint geometry seeds and sensor seeds 55 and 66 for exactly 180 runs. ODI threshold calibration is the 0.95 quantile of Development Open Control frames only.

The immutable detector lock records the threshold, seed split, source/config hashes, development data and summary hashes, code hashes, commit, cleanliness, and environment. Test execution refuses missing or changed locks, dirty source, seed changes, or missing current-commit full-pytest provenance.

## Frozen gates

- Engineering: reproducible clean execution, hash matches, exact run counts, nested mechanisms, no GT trigger dependency, no tracked generated data or caches, and cleaned workspace below 30 MB.
- Geometry mechanism: all 20 test geometry/sensor pairs are nested, PSD, and raw axis-information monotonic.
- Observation mechanism: at least 18 of 20 pairs have strictly decreasing retained axial fraction and normalized axis information.
- Detector: for both sweeps, rho at least 0.75 with bootstrap lower bound above zero, median per-geometry Kendall tau at least 0.67, positive-direction ratio at least 0.80, and paired monotonic rate at least 0.75.
- Direction/control: severe-level alignment median at least 0.95, p10 at least 0.80, stability/actionability at least 0.85, frozen severe trigger rates, and both Open Control false-positive rates at most 0.05.

Only complete passage can set `WEAK_UPDATE_AUTHORIZED=true`. `RISK_WARNING_AUTHORIZED` is fixed to false in Stage 2A.
