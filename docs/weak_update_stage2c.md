# Weak-Subspace Update Stage 2C

Stage 2C replaces normal-equation column scaling with a projected Kalman-gain
update. It remains a synthetic detector-plus-weak-direction study: it does not
integrate FAST-LIO2, use real IMU propagation, implement real association, or
reopen drift-risk prediction.

## Formulation

After Huber whitening, the complete robust gain and correction are

\[
K=P^-A^T(AP^-A^T+I)^{-1}, \qquad \delta_{full}=-Ky.
\]

For normalized weak translation direction (t), lifted into the six-state
space, Stage 2C applies

\[
T=I-(1-\alpha)tt^T, \qquad K_{sel}=TK.
\]

Thus the weak correction is exactly alpha times the complete correction while
rotation and strong translation components are unchanged. Every strategy uses
the Joseph covariance update

\[
P^+=(I-KA)P^-(I-KA)^T+KK^T.
\]

The formal methods are `huber_full`, `huber_global_gain`,
`huber_directional_mode`, `huber_projected_gain`, and the isolated offline
`huber_oracle_projected_gain` diagnostic.

## Stress and split

The main stress is a shared-sign, shared-start, 20-frame coherent axial slip at
1.5 nominal measurement sigma, below the fixed 2.5-sigma Huber threshold.
`gross_outlier_control` is diagnostic only and is excluded from reserved Test.

Development uses the already-seen Stage 2B Test seeds. Reserved Test uses new
geometry seeds 4003 through 5147, sensor seeds 99 and 111, and process seeds
6001 through 6020. The namespaces are required to be disjoint.

An alpha is Development-feasible only if severe geometry and observation
sweeps both improve, each positive-geometry ratio is at least 0.60, safety
limits hold, and no solver fails. Selection maximizes the smaller of the two
sweep improvements; candidates within one percentage point use the largest
alpha. No feasible alpha is `DEVELOPMENT_NO_GO`: no lock and no Test.

## Workflow

```bash
python3 scripts/32_run_weak_update_stage2c.py --quick \
  --run-id weak_update_stage2c_quick_v1
python3 scripts/32_run_weak_update_stage2c.py --development \
  --run-id weak_update_stage2c_dev_v1 --workers 8 --resume
python3 scripts/32_run_weak_update_stage2c.py --lock-update \
  --development-run-dir results/weak_update_stage2c/development/weak_update_stage2c_dev_v1
python3 scripts/32_run_weak_update_stage2c.py --test \
  --run-id weak_update_stage2c_test_v1 \
  --update-lock artifacts/current/weak_update_stage2c/locked/update_lock.json \
  --workers 8 --resume
```

The Test command additionally requires a committed immutable lock, clean source
and config hashes, unchanged Stage 2A and Stage 2B evidence, the reserved seed
set, and full-pytest provenance for the current commit.

## Locked result

Development selected alpha 0.9 as the only feasible candidate. The reserved
Test completed 360 blocks and 36,000 method trials with zero pairing violations
and zero solver failures. Geometry and Observation coherent-stress axis-RMSE
reductions were 0.3720% and 0.4926%, respectively, versus the locked 15%
threshold. Both primary performance gates therefore failed, while engineering,
formulation, stress-mechanism, clean non-inferiority, and Open-Control safety
passed.

Consequently, `PROJECTED_GAIN_UPDATE_PASS=false`,
`FAST_LIO2_INTEGRATION_AUTHORIZED=false`, and
`RISK_WARNING_AUTHORIZED=false`. The complete compact audit is stored in
`artifacts/current/weak_update_stage2c/`.
