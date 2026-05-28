# Day 19 Report - Grouped / LOSO Metric Validation

## Direct Answers

- Day 19 是否完成 grouped / LOSO validation？Yes. It generated grouped metric summary, LOSO selection results, and pass/fail screening tables.
- ODI 在 grouped summary 中是否稳定？No robust conclusion. ODI axis-drift `n_valid_sequences=4`, `sign_consistency=0.75`, `mean_abs_rho=0.0996862954696`.
- ODI 在 LOSO held-out sequence 中是否稳定？No robust conclusion. LOSO rows preserve held-out ODI rho and train-selected metric behavior for every sequence.
- ODI 是否优于 AIS / lambda_min_clamped / condition_number？No. ODI is not consistently superior to AIS / lambda_min_clamped / condition_number under Day 19 screening.
- 是否存在 train 上有效、held-out 崩溃的 metric？Yes; see `results/day30/tables/day19_loso_selection_results.csv`.
- Day 19 是否可以证明 ODI 的稳健漂移预测？No. ODI remains exploratory and is not validated for robust drift prediction.
- 是否允许进入 Day 20 的 controlled / partial validity analysis？Yes.
- 是否允许进入 weak-subspace update？No.

## Grouped Axis-Drift Summary

| metric_name | n_valid_sequences | mean_abs_rho | sign_consistency | best_sequence_count |
|---|---:|---:|---:|---:|
| ODI_median | 4 | 0.0996862954696 | 0.75 | 2 |
| AIS_median | 4 | 0.0689605895691 | 0.75 | 0 |
| lambda_min_clamped_median | 3 | 0.0158541227678 | 0.666666666667 | 1 |
| condition_number_median | 4 | 0.0465005793299 | 0.75 | 1 |

## LOSO Results

| held_out_sequence | target_name | selected_metric_from_train | train_mean_abs_rho | held_out_rho | held_out_validity_status | ODI_held_out_rho |
|---|---|---|---:|---:|---|---:|
| CT-L2-S01-M2 | axis_drift_rate | ODI_median | 0.125737273816 | 0.0215333604313 | valid | 0.0215333604313 |
| OC-L0-S01-M1 | axis_drift_rate | condition_number_median | 0.057565420191 | 0.0133060567464 | valid | -0.227916791073 |
| RT-L4-S01-M1 | axis_drift_rate | ODI_median | 0.112431201839 | -0.061451576363 | valid | -0.061451576363 |
| ST-L3-S01-M1 | axis_drift_rate | ODI_median | 0.103633909289 | -0.0878434540112 | valid | -0.0878434540112 |
| CT-L2-S01-M2 | weak_drift_alignment | lambda_min_clamped_median | 0.0926964090164 | 0.0644882839229 | valid | -0.0471354326471 |
| OC-L0-S01-M1 | weak_drift_alignment | lambda_min_clamped_median | 0.0785923464696 | nan | insufficient_windows | nan |
| RT-L4-S01-M1 | weak_drift_alignment | AIS_median | 0.0836331593908 | 0.0299863704167 | valid | -0.0141534566552 |
| ST-L3-S01-M1 | weak_drift_alignment | lambda_min_clamped_median | 0.0644882839229 | -0.0926964090164 | valid | -0.111195961142 |

LOSO rows with invalid held-out selected metric: `1`.

## Pass / Fail Screening

| metric_name | target_name | final_day19_status | reason |
|---|---|---|---|
| ODI_median | axis_drift_rate | exploratory_not_validated | ODI remains exploratory and is not validated for robust drift prediction. Missing: grouped_validity, best_sequence_support |
| AIS_median | axis_drift_rate | exploratory_not_validated | does not pass all Day 19 screening checks. Missing: baseline_comparison |
| lambda_min_clamped_median | axis_drift_rate | exploratory_not_validated | does not pass all Day 19 screening checks. Missing: sign_consistency, baseline_comparison |
| condition_number_median | axis_drift_rate | exploratory_not_validated | does not pass all Day 19 screening checks. Missing: baseline_comparison |
| ODI_median | weak_drift_alignment | exploratory_not_validated | ODI remains exploratory and is not validated for robust drift prediction. Missing: grouped_validity, baseline_comparison, best_sequence_support |
| AIS_median | weak_drift_alignment | exploratory_not_validated | does not pass all Day 19 screening checks. Missing: baseline_comparison |
| lambda_min_clamped_median | weak_drift_alignment | exploratory_not_validated | does not pass all Day 19 screening checks. Missing: grouped_validity, loso_stability, sign_consistency |
| condition_number_median | weak_drift_alignment | exploratory_not_validated | does not pass all Day 19 screening checks. Missing: sign_consistency, baseline_comparison |

## Conclusion

Day 19 completes grouped / LOSO validation.
It does not authorize weak-subspace update yet.
Day 19 does not authorize weak-subspace update yet.
Day 20 must perform controlled / partial validity analysis before any method update is implemented.
