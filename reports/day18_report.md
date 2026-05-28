# Day 18 Report - Within-Sequence Window Validation

## Direct Answers

- Day 18 是否真正做了 window-level within-sequence validation？Yes. It produced `3440` window rows from Day 17 unbiased trial trajectories.
- Day 17 的 sequence-level per-family undefined 问题是否被修正？Partially. Day 18 evaluates windows inside each sequence, but metrics that remain constant within a sequence are still marked as undefined instead of forced into a correlation.
- 在每条序列内部，ODI / AIS / lambda_min_clamped / condition_number 哪些指标对 axis_drift_rate 有解释趋势？See `results/day30/tables/day18_sequence_validity_summary.csv`; the best metric is reported per sequence rather than merged.
- 是否存在 metric constant 导致无法验证的情况？Yes. `undefined_constant_metric` rows: `12`.
- ODI 是否优于 AIS / lambda_min_clamped？ODI is not consistently superior to AIS / lambda_min_clamped / condition_number.
- Day 18 是否可以证明 ODI 有效？No. Day 18 does not yet prove ODI robustness.
- 是否允许进入 Day 19 的 LOSO / grouped validation？Yes, but only for grouped / LOSO validation; no weak-subspace update is allowed.
- Day 17 unbiased protocol 是否保持？Yes; all window rows must have `applied_axis_bias=0` and `is_unbiased_protocol=true`.

## Sequence Summary

| sequence_id | scene_family | n_trials | n_windows | best_metric_for_axis_drift | best_abs_rho | ODI rho | AIS rho | lambda_min_clamped rho | condition_number rho |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|
| OC-L0-S01-M1 | OC | 20 | 740 | ODI_median | 0.227916791073 | -0.227916791073 | 0.172531392814 | -0.0160667576162 | 0.0133060567464 |
| ST-L3-S01-M1 | ST | 20 | 900 | ODI_median | 0.0878434540112 | -0.0878434540112 | 0.0399336541898 | 0.00852981040715 | -0.0772537388783 |
| CT-L2-S01-M2 | CT | 20 | 820 | lambda_min_clamped_median | 0.02296580028 | 0.0215333604313 | -0.0199496458027 | 0.02296580028 | -0.0158025059429 |
| RT-L4-S01-M1 | RT | 20 | 980 | condition_number_median | 0.0796400157518 | -0.061451576363 | 0.0434276654697 | nan | -0.0796400157518 |

## Undefined / Limited Correlations

| sequence_id | metric_name | target_name | validity_status |
|---|---|---|---|
| OC-L0-S01-M1 | ODI_median | weak_drift_alignment | insufficient_windows |
| OC-L0-S01-M1 | AIS_median | weak_drift_alignment | insufficient_windows |
| OC-L0-S01-M1 | lambda_min_clamped_median | weak_drift_alignment | insufficient_windows |
| OC-L0-S01-M1 | condition_number_median | weak_drift_alignment | insufficient_windows |
| OC-L0-S01-M1 | weak_alignment_median | axis_drift_rate | insufficient_windows |
| OC-L0-S01-M1 | weak_alignment_median | cross_drift_rate | insufficient_windows |
| OC-L0-S01-M1 | weak_alignment_median | weak_drift_alignment | insufficient_windows |
| ST-L3-S01-M1 | weak_alignment_median | axis_drift_rate | undefined_constant_metric |
| ST-L3-S01-M1 | weak_alignment_median | cross_drift_rate | undefined_constant_metric |
| ST-L3-S01-M1 | weak_alignment_median | weak_drift_alignment | undefined_constant_metric |
| CT-L2-S01-M2 | weak_alignment_median | axis_drift_rate | undefined_constant_metric |
| CT-L2-S01-M2 | weak_alignment_median | cross_drift_rate | undefined_constant_metric |
| CT-L2-S01-M2 | weak_alignment_median | weak_drift_alignment | undefined_constant_metric |
| RT-L4-S01-M1 | lambda_min_clamped_median | axis_drift_rate | undefined_constant_metric |
| RT-L4-S01-M1 | lambda_min_clamped_median | cross_drift_rate | undefined_constant_metric |
| RT-L4-S01-M1 | lambda_min_clamped_median | weak_drift_alignment | undefined_constant_metric |
| RT-L4-S01-M1 | weak_alignment_median | axis_drift_rate | undefined_constant_metric |
| RT-L4-S01-M1 | weak_alignment_median | cross_drift_rate | undefined_constant_metric |
| RT-L4-S01-M1 | weak_alignment_median | weak_drift_alignment | undefined_constant_metric |

Valid within-sequence correlations: `41`.

## Conclusion

Day 18 performs window-level within-sequence validation.
It does not yet prove ODI robustness.
Day 19 must perform grouped / LOSO validation before any weak-subspace update is implemented.
