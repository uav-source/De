# Stage 2 Failure-Mechanism Diagnosis — Day 8 Logging Contract

## Scope

Day 8 adds read-only, per-frame diagnostics to the existing Stage 2B/2C estimator loop. Its only purpose is to align three causal observations: whether the measurements push persistently along the online weak direction, how much the unmodified full Huber update and the applied update move along that direction, and whether the applied update reduces the offline ground-truth axial error.

Day 8 does not develop a new algorithm. It does not change ODI, the translation Schur information matrix, whitening or scale definitions, direction reliability thresholds, the online ODI threshold, Huber delta, Stage 2B alpha, Stage 2C projected-gain parameters, process noise, correspondence stress, seeds, or statistical gates. It adds no estimator, gate, bias state, threshold sweep, or window statistic.

Day 8 is private internal research while Patent 1 remains unfiled. It is not authorization for public disclosure or a claim that Stage 1, Stage 2, Stage 3, or Degen-LIO is complete.

## State order, coordinates, and perturbation convention

The existing correction state is frozen as

```text
delta = [delta_theta_x, delta_theta_y, delta_theta_z,
         delta_p_x,     delta_p_y,     delta_p_z]
```

`src/minibench/map_lio.py` linearizes rotation with the existing local/right perturbation convention. `src/minibench/motion_simulator.py::apply_se3_increment` applies `delta_theta` on the right and adds `delta_p` directly in the world frame. Consequently:

- rotation increments remain local/right perturbations;
- translation updates are in the world frame;
- logged weak translation directions are in the world frame;
- every translation projection is performed in that common world frame.

The online weak direction is `primary_weak_dir_[x,y,z]` from the normalized translation Schur information eigensystem. It is already the detector's physical three-dimensional world-frame direction. The logger never substitutes the last three entries of a six-dimensional whitened eigenvector and never uses a body-frame translation direction.

## Weak-direction sign continuity

The detector's first valid direction retains its canonical sign: the largest-magnitude component is nonnegative. For later valid frames, `orient_direction_for_logging` normalizes the current direction and compares it with the previous valid logged direction. If their dot product is negative, the logged direction is multiplied by `-1` and `weak_direction_sign_flipped=true`.

This sign orientation is diagnostic only. It does not modify detector output, triggering, the actionable decision, the update direction, the trajectory, or covariance. An unreliable, non-finite, or effectively zero current direction is invalid; the previous direction is not reused as a substitute. Direction-dependent fields are then NaN rather than zero.

## Directional weak-innovation score

For the logged physical world-frame direction `v`, define

```text
d = [0, 0, 0, v_x, v_y, v_z]^T.
```

The unmodified measurement score uses the current prior linearization and observation variances:

```text
H_raw = J^T diag(1 / R_i) J
b_raw = J^T diag(1 / R_i) r
h_raw = d^T H_raw d
g_raw = -d^T b_raw
z_parallel_raw = g_raw / sqrt(h_raw)
```

The Huber score reuses, without recomputation of robust weights, the current `build_robust_linear_system()` outputs:

```text
h_huber = d^T H d
g_huber = -d^T b
z_parallel_huber = g_huber / sqrt(h_huber)
```

The sign convention is fixed: positive `z` means the LiDAR score recommends a correction along `+v`; negative `z` means it recommends `-v`. Both gradients and directional information values are logged with the final score.

These values are directional score statistics, not a complete Kalman NIS. The documentation, schemas, and runner do not label them NIS.

`directional_information_epsilon` is frozen at `1.0e-12`. If directional information is not greater than this value, the innovation is invalid and `z` is NaN. The implementation never divides by the epsilon to manufacture a large score.

## Full and applied update projections

The full update is strictly the existing `huber_full` gain update evaluated from the same prior pose, prior covariance, Jacobian, residual, variances, and Huber weights as the applied method. When the applied method is `huber_full`, the already-solved result is reused. For `huber_projected_gain`, the existing full result is a shadow diagnostic only; it is not applied to the trajectory, posterior covariance, or next-frame prior.

For a full correction `delta_full`, the logger records

```text
u_weak_full   = v^T delta_p_full
u_strong_full = (I - vv^T) delta_p_full
u_rotation    = ||delta_theta_full||_2.
```

It retains the signed weak component, its absolute value, the three-dimensional strong vector and norm, the rotation norm, every correction component, the full solver condition number, and the full posterior covariance trace. The same physical projections are logged for the actually applied strategy so a later analysis can distinguish an intrinsically small full update from a selective update that changes the correction but has little trajectory effect.

## Online/offline separation

`src/eval/stage2_failure_logging.py` accepts only current-frame online quantities. It has no ground-truth pose, scene axis, scene label, oracle direction, or future-frame input, and it does not import the offline evaluator.

`src/eval/stage2_failure_gt_metrics.py` is the only Day 8 module that receives ground truth. With world-frame scene axis `a`, it computes

```text
e_prior = p_prior - p_gt
e_post  = p_post  - p_gt

prior_axis_error_signed_m     = a^T e_prior
posterior_axis_error_signed_m = a^T e_post

axis_abs_error_change_m = |a^T e_post| - |a^T e_prior|
axis_abs_error_reduction_m = |a^T e_prior| - |a^T e_post|.
```

A positive reduction means the frame update reduced axial error; a negative reduction means it worsened axial error. The offline evaluator may also project these errors onto the online logged weak direction. Every offline row is marked `offline_evaluation_only=true`, and no offline value is returned to the estimator or online logger.

## Files, schemas, and NaN semantics

Each Quick run writes separate, one-to-one joinable files:

```text
results/stage2_failure_analysis/day8_quick/<run_id>/
  frame_diagnostics_online.csv
  frame_diagnostics_gt.csv
  run_manifest.json
  day8_quick_summary.json
```

The schemas are fixed as `stage2_failure_online_v1` and `stage2_failure_gt_v1`. CSV column order comes from explicit schema lists, never mapping iteration order. Validators require complete unique frame keys, unit valid directions, positive residual counts, Huber weights in `(0, 1]`, valid outlier ratios, and finite successful-solver covariance diagnostics. Online field names and logger inputs exclude ground-truth and oracle data.

NaN has a narrow, legal meaning. It marks a quantity that is undefined because the current weak direction is invalid, directional information is insufficient, or the explicitly flagged full solve failed. NaN is not replaced by zero, because zero would falsely claim a measured absence of innovation or update.

## Quick fixture and equivalence

`day8_unit_fixture_v1` is a deterministic, dedicated eight-frame engineering fixture. Its identifiers are disjoint from Development and Reserved Test seeds. Quick runs only `huber_full` and the repository's actual `huber_projected_gain` method. It is not a formal clean/coherent comparison and cannot execute Development, Validation, Test, Reserved Test, threshold analysis, or a formal Stage 2C rerun.

Logging-enabled and logging-disabled runs use identical observations, motion, stress, initial state, covariance, and method. The contract requires prior poses, posterior poses, applied deltas, posterior covariances, detector triggers, and actionable flags to agree to an absolute tolerance of `1.0e-12`; discrete fields must agree exactly. The logger does not mutate arrays, sample random values, change measurement order, robust weights, covariance, or update results.

## Explicit exclusions and current status

Day 8 contains no window mean, median, same-sign run length, CUSUM, autocorrelation, skewness, AUROC, FPR, or joint gate. Those belong to later diagnosis stages and are not preimplemented here.

The current prototype still has no FAST-LIO2 integration, real IMU propagation, or real data association. It remains a controlled synthetic degeneration detector and weak-direction research prototype, not a complete Degen-LIO system.

Successful Day 8 logging can only report:

```text
DAY8_LOGGING_PASS = true
STAGE2_GATE = INCOMPLETE
STAGE3_GATE = NOT_STARTED
RISK_WARNING_AUTHORIZED = false
FAST_LIO2_INTEGRATION_AUTHORIZED = false
PUBLIC_DISCLOSURE_AUTHORIZED = false
```
