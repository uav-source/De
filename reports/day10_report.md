# Day 10 Report - Metric Validity Comparison

## Completed Items

- Implemented `src/eval/stats.py`.
  - `spearman_corr(x, y)`
  - `pearson_corr(x, y)`
  - `bootstrap_ci_corr(x, y, n_boot=1000, random_seed=42)`
  - `safe_auc_if_binary_available(score, label)`
  - `rank_metrics_by_correlation(metric_table, target)`
  - `leave_one_sequence_out_correlation(rows, metric_name, target_name)`
- Implemented `scripts/05_metric_validity.py`.
- Added `tests/test_stats.py`.
- Updated `scripts/reproduce_day14.sh` to include the Day 10 validity step.

## Reproducibility Record

- Date: 2026-05-28
- Repository: `/home/lj/Degen-LIO`
- Base git commit at run start: `72b832e`
- Detector config: `configs/detector/odi_default.yaml`
- Random seed: `42`
- Window count used by Day 10: `172`
- High drift flag: `axis_drift_rate > global 75th percentile`

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
```

## Verification

- `python3 scripts/check_env.py`: OK
- `python3 -m pytest -q`: `69 passed in 2.22s`

## Output Files

- `results/day14/tables/day10_metric_validity.csv`
- `results/day14/tables/day10_metric_validity_per_sequence.csv`
- `results/day14/tables/day10_metric_validity_loso.csv`

## Merged Correlation Summary

Merged all-sequence axis-drift correlation:

| metric | Spearman rho | Pearson r | bootstrap CI |
|---|---:|---:|---:|
| ODI | 0.647276 | 0.961975 | [0.541763, 0.745680] |
| condition_number | 0.492916 | 0.961233 | [0.340253, 0.615807] |
| lambda_min_clamped | -0.711978 | -0.961096 | [-0.784596, -0.612706] |
| AIS | -0.897659 | -0.969738 | [-0.919365, -0.862679] |

Merged high-axis-drift flag:

| metric | Spearman rho | raw AUC |
|---|---:|---:|
| ODI | 0.337080 | 0.724716 |
| condition_number | 0.203765 | 0.635839 |
| lambda_min_clamped | -0.363604 | 0.285199 |
| AIS | -0.675647 | 0.049576 |

Merged weak-drift-alignment correlation:

| metric | Spearman rho | valid samples |
|---|---:|---:|
| ODI | 0.307107 | 135 |
| condition_number | -0.022089 | 135 |
| lambda_min_clamped | -0.354826 | 135 |
| AIS | -0.585060 | 135 |

## Per-Sequence Summary

ODI versus axis drift within each sequence:

| sequence_id | ODI Spearman rho | p-value |
|---|---:|---:|
| OC-L0-S01-M1 | -0.025130 | 0.882628 |
| ST-L3-S01-M1 | -0.145586 | 0.339964 |
| CT-L2-S01-M2 | 0.141986 | 0.375867 |
| RT-L4-S01-M1 | -0.288673 | 0.044262 |

The per-sequence results do not support a stable positive ODI-axis-drift
relationship. Several sequence-internal correlations are weak or negative.

## Leave-One-Sequence-Out Summary

ODI versus axis drift:

| held_out_sequence | train rho | held-out rho |
|---|---:|---:|
| CT-L2-S01-M2 | 0.571446 | 0.141986 |
| OC-L0-S01-M1 | 0.291586 | -0.025130 |
| RT-L4-S01-M1 | 0.758110 | -0.288673 |
| ST-L3-S01-M1 | 0.740181 | -0.145586 |

The leave-one-sequence-out check is not stable. Training correlations can look
strong after mixing sequence families, but held-out sequence correlations do
not preserve the same trend.

## Ranking

For merged axis drift, ranking by absolute Spearman magnitude is:

1. `AIS`: `|rho|=0.897659`
2. `lambda_min_clamped`: `|rho|=0.711978`
3. `ODI`: `|rho|=0.647276`
4. `condition_number`: `|rho|=0.492916`

For the raw high-axis-drift AUC, without sign flipping:

1. `ODI`: `AUC=0.724716`
2. `condition_number`: `AUC=0.635839`
3. `lambda_min_clamped`: `AUC=0.285199`
4. `AIS`: `AUC=0.049576`

Low `AIS` and low `lambda_min_clamped` correspond to worse degeneracy, so their
negative correlations are expected. Day 10 does not flip signs post hoc.

## Bias Audit

- Merged correlation may be amplified by Day 7 scene-family `axis_bias`: yes.
  Tunnel scenes have both higher ODI and stronger injected axis drift than OC,
  so merged all-sequence correlation is not enough.
- Per-sequence correlation still supports ODI: no. ODI is not consistently
  positive inside individual sequences.
- Leave-one-sequence-out is stable: no. Held-out sequence correlations are weak
  or negative for the axis-drift target.
- ODI is at least better than one traditional metric: partially yes. On merged
  axis drift, ODI beats `condition_number` by absolute Spearman magnitude and
  has higher raw high-drift AUC. It does not beat `lambda_min_clamped` or `AIS`
  by absolute Spearman magnitude.
- Claim status: the claim must be reduced. The toy probe shows a merged
  all-sequence ODI signal, but not a sequence-internal or leave-one-sequence-out
  robust validity result. This cannot be used as a paper main experiment
  conclusion.

## Day 14 Gate Status

- ODI vs axis drift Spearman rho >= 0.50 initial signal: merged-only yes,
  `rho=0.647276`. Bias-audited evidence is not yet sufficient.
- ODI beats condition_number or lambda_min on at least one primary drift target:
  yes versus `condition_number` on merged axis drift, no versus
  `lambda_min_clamped` or `AIS`.
- Sensitivity is still not tested.
- Figures, Day 14 gate table, final manifest, and final Go/Conditional Go/No-Go
  report are still not implemented.

## Failed Items

- None in script execution.
- Scientific validity warning: per-sequence and LOSO checks do not yet support a
  robust ODI-drift claim.

## Day 11 Most Important Task

- Implement sensitivity checks for whitening/scales and `tau_w`.
- Preserve the Day 10 audit: all conclusions must separate merged,
  per-sequence, and leave-one-sequence-out evidence.
