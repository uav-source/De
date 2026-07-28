# Phase A v1.1 Provenance Contract Invalidation

The Phase A v1.1 pre-run integrity checks passed, but its first formal snapshot
build stopped at the bytewise round-trip provenance assertion before any
snapshot result was committed and before Open3D or PCL was called.

The invalid assertion effectively required
`Q32(T_reference * Q32(inverse(T_reference) * p_target)) == Q32(p_target)`.
Float32 quantization does not commute with a general SE(3) transform, so this
identity is not guaranteed even when source points have correct target-parent
lineage.  The v1.1 formal-run authorization is therefore invalidated.

This is an implementation provenance-contract defect.  It is not an Open3D,
PCL, registration, qualification-Gate, or scientific-hypothesis failure.  No
backend result or scientific pose error was exposed.  The original v1.1 lock
and artifact remain unchanged as historical evidence.
