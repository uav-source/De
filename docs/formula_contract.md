# Formula Contract

This file freezes the Day 1-14 math interface. Code, logs, and reports must use
the same symbols and dimensions.

## Pose Perturbation Block

Only the 6DoF pose block is analyzed:

```text
delta x_p = [delta theta^T, delta p^T]^T in R^6
```

The first three components are rotation perturbation. The last three
components are translation perturbation.

## Point-To-Plane Linearization

For a LiDAR point `p_i` transformed by pose `(R, t)` and matched to a local
plane with unit normal `n_i` and anchor point `q_i`:

```text
r_i = n_i^T (R p_i + t - q_i)
r_i ~= r_i0 + J_i delta x_p
```

The Jacobian row is:

```text
J_i = [n_i^T (-R [p_i]_x), n_i^T] in R^(1x6)
```

For a frame with `m` residuals:

```text
J_p = [J_1^T, ..., J_m^T]^T in R^(m x 6)
r_L in R^m
R_L = diag(sigma_1^2, ..., sigma_m^2) in R^(m x m)
```

## Pose-Scale Whitening

The state-scale matrix is:

```text
D = diag(s_theta I_3, s_p I_3) in R^(6x6)
delta x_p = D xi
```

The whitened pose information matrix is:

```text
H_tilde = (J_p D)^T R_L^-1 (J_p D) in R^(6x6)
```

`H_tilde` must be symmetric positive semidefinite up to numerical tolerance.

Important forbidden operation:

```text
Do not left-multiply LiDAR residuals by a state-space projection matrix.
```

State subspace operations belong in the state/update coordinates, not as an
invalid residual-space left multiplication.

## Spectrum

Eigen-decomposition:

```text
H_tilde = V Lambda V^T
Lambda = diag(lambda_1, ..., lambda_d), d = 6
lambda_1 >= ... >= lambda_d >= 0
```

All eigenvalues used by metrics must be clipped only for numerical safety, not
for result manipulation.

## ODI

With small positive `epsilon`:

```text
p_i = (lambda_i + epsilon) / sum_j(lambda_j + epsilon)
r_eff = exp(-sum_i p_i log p_i)
ODI = 1 - (r_eff - 1) / (d - 1), d = 6
```

Interpretation:

- `ODI ~= 0`: spectrum is close to uniform.
- `ODI ~= 1`: spectrum is concentrated and low effective rank.

ODI describes spectral concentration. It does not alone describe absolute
information strength.

## Absolute Information Strength

AIS must be reported with ODI:

```text
AIS = logdet(H_tilde + epsilon I) / d
```

AIS is used to catch the case where all directions have low information but the
spectrum is not strongly concentrated.

## Alternative Metrics

The following alternatives must be exported for comparison:

```text
lambda_min = min_i lambda_i
condition_number = lambda_max / max(lambda_min, epsilon)
```

Day 14 must compare ODI against `condition_number` and `lambda_min`; ODI cannot
be reported alone.

## Weak Subspace

Weak eigenvectors are selected by:

```text
V_W = {v_i | lambda_i / lambda_1 < tau_w}
```

The primary weak direction is the eigenvector associated with `lambda_min`,
unless reliability checks mark it invalid.

For alignment with tunnel geometry, compare only the translation component:

```text
v_p = normalize(v_weak[3:6])
axis_alignment = |v_p^T a|
```

where `a` is the unit tunnel axis or local centerline tangent. If `||v_p||` is
too small or the spectrum is isotropic, the weak direction must be marked
unreliable instead of forcing an alignment value.

