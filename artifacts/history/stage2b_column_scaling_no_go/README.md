# Stage 2B Column-Scaling NO-GO

This directory freezes the compact evidence from Weak-Subspace Update Stage 2B.
The selective update failed its locked Geometry and Observation severe-stress
gates. FAST-LIO2 integration and risk warning were not authorized.

## Why the formulation failed

The legacy update used

```text
H_old = A^T H A
b_old = A^T b
```

In a one-dimensional weak direction this becomes

```text
H_old = alpha H
b_old = sqrt(alpha) b

delta_old = -sqrt(alpha) b / (Lambda_prior + alpha H)
```

When measurement information dominates the prior,
`H >> Lambda_prior`, so

```text
delta_old ~= delta_full / sqrt(alpha)
```

Therefore a smaller alpha can make the weak-direction correction larger. This
gradient/information scaling mismatch invalidates the intended attenuation
semantics even though the transformed information matrix remains PSD.

## Frozen outcome

- Stage 2B selective update: **FAIL**
- FAST-LIO2 integration: **NOT AUTHORIZED**
- Risk warning: **NOT AUTHORIZED**
- Historical commit: `c5fe3c5`
- Historical tag: `archive/weak-update-stage2b-no-go`

The original generated data and results are intentionally not included here.
Only the compact lock, gate tables, manifest, and reports are retained.
