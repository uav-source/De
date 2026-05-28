# Day 12 Report - Sensitivity and Stability Diagnosis

## Completed Items

- Stabilized plotting tests by adding `timeout=120` to `tests/test_plot_day14.py`.
- Confirmed `scripts/04_plot_day14.py` closes every figure with `plt.close(fig)` after saving.
- Implemented `scripts/06_sensitivity.py`.
- Added `tests/test_sensitivity.py`.
- Generated sensitivity tables:
  - `results/day14/tables/day12_sensitivity_D.csv`
  - `results/day14/tables/day12_sensitivity_tau.csv`
- Generated sensitivity figures:
  - `results/day14/figures/Fig_D14_08_sensitivity_D.png`
  - `results/day14/figures/Fig_D14_08_sensitivity_D.pdf`
  - `results/day14/figures/Fig_D14_09_sensitivity_tau.png`
  - `results/day14/figures/Fig_D14_09_sensitivity_tau.pdf`

## Reproducibility Record

- Date: 2026-05-28
- Repository: `/home/lj/Degen-LIO`
- Base git commit at run start: `1f8691c`
- Day 12 implementation commit: `375cdda`
- Detector config: `configs/detector/odi_default.yaml`
- Random seed: `42`
- D grid:
  - `s_theta in [0.02, 0.05, 0.10]`
  - `s_p in [0.2, 0.5, 1.0]`
- `tau_w` grid: `[0.005, 0.01, 0.02, 0.05]`
- OC high-degeneracy threshold used for false-positive ratio: `ODI >= 0.70`

## Run Commands

```bash
python3 scripts/check_env.py
python3 -m pytest -q
python3 scripts/00_generate_minibench.py --all
python3 scripts/01_simulate_observations.py --all --config configs/detector/odi_default.yaml
python3 scripts/02_compute_odi.py --all --config configs/detector/odi_default.yaml
python3 scripts/02_run_toy_lio.py --all --config configs/detector/odi_default.yaml
python3 scripts/03_eval_metrics.py --all --config configs/detector/odi_default.yaml
python3 scripts/05_metric_validity.py --config configs/detector/odi_default.yaml
python3 scripts/04_plot_day14.py --results results/day14 --out results/day14/figures
python3 scripts/06_sensitivity.py --config configs/detector/odi_default.yaml --results results/day14 --out results/day14/tables
```

## Verification

- `python3 scripts/check_env.py`: OK
- `python3 -m pytest -q`: `73 passed in 18.17s`

## D Sensitivity Summary

| quantity | valid-grid min | valid-grid max |
|---|---:|---:|
| `ODI_median` | 0.296698 | 0.784393 |
| merged ODI-axis Spearman rho | 0.612929 | 0.666495 |
| ST median axis alignment | 1.0 | 1.0 |
| CT median axis alignment | 1.0 | 1.0 |
| RT median axis alignment | 1.0 | 1.0 |
| OC false reliable ratio | 0.0 | 0.0 |
| OC false high-degeneracy ratio | 0.0 | 0.0 |
| per-sequence rho min | -0.292653 | -0.149934 |
| per-sequence rho max | 0.048878 | 0.148258 |

- Valid D points: `8 / 9`.
- Invalid D point: `s_theta=0.02, s_p=1.0`, marked `valid_sensitivity_point=0` with `notes=nan_or_missing_required_metric`.
- This invalid point is not counted as a success.

## Tau Sensitivity Summary

| quantity | tau-grid min | tau-grid max |
|---|---:|---:|
| `ODI_median` | 0.727896 | 0.727896 |
| merged ODI-axis Spearman rho | 0.647276 | 0.647276 |
| ST median axis alignment | 1.0 | 1.0 |
| CT median axis alignment | 1.0 | 1.0 |
| RT median axis alignment | 1.0 | 1.0 |
| OC false reliable ratio | 0.0 | 0.0 |
| OC false high-degeneracy ratio | 0.0 | 0.0 |
| per-sequence rho min | -0.288673 | -0.288673 |
| per-sequence rho max | 0.141986 | 0.141986 |

All four tau points are valid under the current primary-weak-direction reliability logic.

## Required Answers

- ODI stability to D: partially stable. The merged ODI-axis rho stays positive and above `0.50` for the valid D grid, but the ODI magnitude changes substantially and one extreme D point invalidates weak-direction alignment.
- Weak direction alignment stability to `tau_w`: stable in this implementation. ST/CT/RT median axis alignment remains `1.0` for all tau values.
- OC false reliable weak-direction ratio: controlled. It stays `0.0` for all valid D and tau points.
- OC false high-degeneracy ratio: controlled under the fixed `ODI >= 0.70` threshold. It stays `0.0`.
- Merged rho only at default parameters: no. The merged positive ODI-axis rho persists across the valid D grid and all tau values.
- Per-sequence instability still exists: yes. Across D, per-sequence rho remains weak or negative in at least one sequence; across tau, the same Day 10 per-sequence instability remains unchanged.
- Day 14 decision: **CONDITIONAL GO** for completing the Day 14 minimum gate report. It is not a GO for a robust ODI drift-prediction claim.

## Interpretation

The sensitivity result strengthens the narrow statement that the merged synthetic ODI-axis signal is not a single-default-parameter accident. It also preserves the Day 10 warning: sequence-internal and leave-one-sequence-out evidence remain unstable, and AIS/`lambda_min_clamped` remain serious competitors. The current evidence supports continuing the Day 14 diagnostic package, but any method or paper claim must remain reduced.

## Failed Items

- No script execution failures.
- One D sensitivity point was invalid and was explicitly recorded rather than treated as success.

## Day 13 Most Important Task

- Build the Day 14 gate table and final manifest from generated artifacts.
- Preserve the status split: merged signal positive, per-sequence and LOSO robustness not established.
