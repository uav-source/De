# Zero-Perturbation Dual-Backend Phase A v1.2 Stage-0 Protocol

## Amendment boundary

Version 1.2 is an implementation-only provenance and execution-staging
amendment. The frozen Phase A scientific contract remains unchanged: seven
scenes, three Development geometry seeds, two Development measurement seeds,
five repeats, IDEAL_MATCHED only, 210 snapshots, 420 planned trials, both
backend parameter sets, transform semantics, metrics, failure definitions,
qualification Gates, linear q95, and the per-scene snapshot-diversity Gate.

The v1.1 formal attempt reached the first snapshot builder but completed no
snapshot, executed no backend, wrote no trial result, and exposed no scientific
result. Its bytewise round-trip assertion is permanently invalid because
float32 quantization does not commute with a general SE(3) transform. This is
not an Open3D, PCL, Phase A, or scientific-hypothesis failure.

## Canonical target and indexed lineage

The frozen scene generator produces the target map once for each snapshot. It
is converted exactly once to little-endian, C-contiguous float32. Every source
parent is then read by an int64 index from that exact canonical target array;
the original float64 scene output cannot serve as a second lineage reference.

Eligible parents satisfy the already frozen inclusive reference-range rule of
0.30 to 20.0 metres. The v1 scientific contract also requires measurement seed
and repeat to control only source-subset selection. To implement that frozen
intent deterministically without dropout or an RNG, each eligible parent is
hashed with the exact UTF-8 payload

```
phase-a-v1.2-parent-selection|scene={scene}|geometry_seed={geometry_seed}|measurement_seed={measurement_seed}|repeat={repeat}|parent_index={parent_index}
```

using SHA-256. The parent is retained when the first digest byte modulo four is
nonzero. Eligible target order is preserved. This rule is frozen before any
v1.2 formal snapshot is built and cannot be adapted after observing Stage 0.

For reference rotation `R`, translation `t`, and selected canonical target
parent `p_parent`, source coordinates are computed in float64 as
`R.T @ (p_parent - t)` and then quantized exactly once to canonical float32.
The future Open3D and PCL stages must read the same cached source, target, and
reference-pose arrays; Stage 1 may not regenerate or requantize them.

## Float32 quantization closure

Bytewise equality after transforming the float32 source back to the target is
not required. Let `p_q` be the float32 source promoted to float64 and `p_s` the
pre-quantization float64 source. Stage 0 computes:

```
actual     = R @ p_q + t - p_parent
source_q   = p_q - p_s
predicted  = R @ source_q
residual   = actual - predicted
scale      = max(1, ||p_parent||2, ||p_s||2, ||t||2)
guard      = 256 * finfo(float64).eps * scale
```

Every point must satisfy `||residual||2 <= guard` and
`||actual||2 <= ||predicted||2 + guard`. The maximum normalized residual ratio
must be at most one. Median and q95 use `numpy.median` and
`numpy.quantile(..., 0.95, method="linear")`. The coefficient, norm, scale,
formula, and comparisons are prospectively fixed.

## Cache, resume, and independent verification

Each snapshot is written into a temporary sibling directory. Array and metadata
files are flushed and fsynced before an atomic directory rename. Existing valid
snapshots are reusable in resume mode; any corrupt, partial, mismatched, extra,
or silently overwritten snapshot stops the run. NumPy arrays are always loaded
with `allow_pickle=False`.

The independent verifier reads the plan, protocol lock, metadata, and arrays
from disk and recomputes identities, dtypes, shapes, order, raw checksums,
parent ranges and uniqueness, indexed lineage, quantization closure, and
per-scene diversity. It does not call the builder's snapshot or analysis
functions. Any disagreement with the builder analysis blocks Stage 1.

## Stage boundary and seed continuation

Stage 0 builds and audits exactly 210 snapshots. It imports and executes no
Open3D, PCL, PCL CLI, or Native registration code and creates no trial result.
The Stage 1 runner requires a verified v1.2 snapshot lock and is not executed in
this round.

Continuation of the unchanged formal Development seed set is justified only
because the v1.1 abort occurred before backend execution and before scientific
result exposure. The correction follows from general floating-point behavior,
not observed scene or backend results. Confirmatory and old capture-range Test
seeds remain forbidden.

Stage 0 authorizes the next Stage 1 round only if protocol-lock integrity, seed
continuation, all 210 cache entries, lineage, closure, cache checksums,
diversity, independent agreement, and artifact verification all pass, with
zero backend executions and zero trial results. Regardless of a Stage 0 pass,
Phase A remains incomplete and Day 1 scientific validation remains
`NOT_EVALUATED` in this round.
