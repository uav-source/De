# Day 17 Report - Unbiased Multi-Trial Metric Probe

## Direct Answers

- Day 17 是否真正运行了 multi-trial unbiased probe？Yes. It ran `20` trials for each of OC/ST/CT/RT.
- 所有 applied_axis_bias 是否为 0？Yes.
- 去掉 scene-family axis_bias 后，ODI / AIS / lambda_min_clamped / condition_number 哪些指标仍然和 drift 有相关趋势？See `results/day30/tables/day17_metric_drift_correlations.csv`; these are exploratory correlations only.
- merged correlation 是否仍可能误导？Yes. Even without axis_bias, merged correlation can still reflect scene-family grouping and static geometry differences.
- per-scene-family correlation 是否稳定？No conclusion yet. Many per-scene-family correlations are undefined because spectral metrics are constant within a single scene family across trials.
- Day 17 是否可以证明 ODI 有效？No. Day 17 does not yet validate ODI.
- 是否允许进入 Day 18 的 within-sequence validation？Yes, but only for stricter validation; no method update is allowed.

## Trial Summary

| sequence_id | scene_family | n_trials | final_axis_error_median | axis_drift_rate_median | all_applied_axis_bias_zero |
|---|---|---:|---:|---:|---|
| OC-L0-S01-M1 | OC | 20 | 1.27033944324e-05 | 1.11747335791e-05 | true |
| ST-L3-S01-M1 | ST | 20 | 0.0461779419154 | 0.000337511473187 | true |
| CT-L2-S01-M2 | CT | 20 | 0.0434639324451 | 0.000394264580581 | true |
| RT-L4-S01-M1 | RT | 20 | 0.035894182149 | 0.000308331416119 | true |

## Merged Exploratory Correlations

| metric_name | target_name | spearman_rho | n |
|---|---|---:|---:|
| ODI_median | final_axis_error | 0.613431663677 | 80 |
| ODI_median | axis_drift_rate_median | 0.465278475764 | 80 |
| AIS_median | final_axis_error | -0.599391002077 | 80 |
| AIS_median | axis_drift_rate_median | -0.410084150856 | 80 |
| lambda_min_clamped_median | final_axis_error | -0.750058600617 | 80 |
| lambda_min_clamped_median | axis_drift_rate_median | -0.57504492714 | 80 |
| condition_number_median | final_axis_error | 0.562594785471 | 80 |
| condition_number_median | axis_drift_rate_median | 0.480771619598 | 80 |

Per-scene-family correlation rows with undefined rho: `32`.

## Conclusion

Day 17 runs an unbiased multi-trial toy probe and provides exploratory metric-drift evidence.
It does not yet validate ODI.
Day 18 must perform stricter within-sequence validation before any method update is implemented.
