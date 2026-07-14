# Stage 2C Compact Audit

This directory records the locked Weak-Subspace Update Stage 2C result. The
implementation was tested at commit `e6b0eb4f697c57df9c2b5808ba03e6b605e43564`
with update definition `projected_gain_stage2c_v1` and attenuation alpha 0.9.

## Scope and integrity

- Development: 540 sensor-stress blocks and 27,000 formal method trials.
- Reserved Test: 360 sensor-stress blocks and 36,000 formal method trials.
- Test pairing groups: 7,200; pairing violations: 0.
- Solver failures: 0.
- Full pytest provenance: 176 passed for the locked Test commit.
- Update lock: `locked/update_lock.json`.
- Update-lock SHA-256: `e19a1d9b84a597aeb6071cd8d8c3fa904829f9b671eff2e3bf031cc905e82fb1`.

The formal estimator does not read ground-truth directions. The oracle method
is an isolated offline diagnostic. Stage 2C does not integrate FAST-LIO2, use
real IMU propagation, implement real data association, or constitute a
complete Degen-LIO system.

## Development

Alpha 0.9 was the only feasible candidate. Its severe coherent-stress median
axis-RMSE reductions were 0.4505% for Geometry and 0.4751% for Observation;
both positive-improvement geometry ratios were 1.0.

The coherent 1.5-sigma stress had a 3.9447% median contaminated-point Huber
downweight ratio in Development. The 4.0-sigma gross-outlier diagnostic had a
62.5% median ratio, confirming that the primary stress usually remained below
the robust loss rejection regime.

## Reserved Test outcome

The direction of the effect reproduced, but its magnitude was far below the
locked 15% primary threshold:

- Geometry median axis-RMSE reduction: 0.3720%; bootstrap 95% CI
  [0.2793%, 0.4790%]; positive-geometry ratio 1.0.
- Observation median axis-RMSE reduction: 0.4926%; bootstrap 95% CI
  [0.3847%, 0.5704%]; positive-geometry ratio 1.0.
- Clean median changes: axis +2.7454%, strong translation +0.0684%,
  orientation +0.0012%, trajectory +1.8944%.
- Open-Control median changes: strong translation +0.3610%, orientation
  -0.00035%, trajectory +0.2288%, q95 update norm -0.00029%.
- Relative to global-gain scaling, projected gain improved severe axis RMSE by
  0.0038% in both sweeps and strong translation by 1.1484% / 2.1542%; the
  locked 5% protection advantage was not met.
- Relative to directional-mode attenuation, projected gain improved axis RMSE
  by 0.2840% / 0.3804%, while strong translation changed by +0.1229% / +0.0310%.
- Oracle coverage: 1,600 total pairs, 1,088 positive-oracle pairs, 68.0%
  conditional coverage.

Final gates:

- `ENGINEERING_PASS`
- `FORMULATION_PASS`
- `STRESS_MECHANISM_PASS`
- `DEVELOPMENT_PASS`
- `GEOMETRY_COHERENT_STRESS_FAIL`
- `OBSERVATION_COHERENT_STRESS_FAIL`
- `CLEAN_NONINFERIORITY_PASS`
- `OPEN_CONTROL_SAFETY_PASS`
- `PROJECTED_GAIN_UPDATE_FAIL`
- `FAST_LIO2_INTEGRATION_AUTHORIZED=false`
- `RISK_WARNING_AUTHORIZED=false`

The evidence supports a NO-GO for projected weak-direction LiDAR attenuation
as a sufficient Degen-LIO mechanism. A future stage would need explicit IMU
direction constraints or historical-state constraints rather than another
attenuation-alpha search.
