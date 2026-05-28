# Day 20 Report - Controlled / Partial Validity Analysis

## Direct Answers

- Day 20 是否完成 controlled / partial validity analysis？Yes. It produced partial correlations, controlled regression summaries, permutation tests, and incremental validity decisions.
- 控制 AIS、lambda_min、condition_number 后，ODI 是否还有增量解释力？No validated incremental ODI evidence under the Day 20 criteria.
- ODI 的 observed sign 是否符合 expected sign？For merged axis drift: `true` with rho `0.0221895295386`.
- Day 19 中“可计算 rho 很小”的问题是否被重新筛查？Yes. Day 20 requires `abs(partial rho) >= effect_size_threshold`; computable small effects are not treated as substantive.
- permutation test 是否支持 ODI？For merged axis drift: `false` with p-value `0.268656716418`.
- ODI 是否优于或至少不弱于 AIS / lambda_min_clamped / condition_number？No. Baseline competition remains a limitation.
- Day 20 是否可以证明 ODI 的稳健漂移预测能力？No.
- 是否允许进入 weak-subspace update？No, unless a controlled-validity signal is later integrated and confirmed through joint-risk evidence.
- 是否允许进入 Day 21 joint risk feature analysis？Yes.

## Merged Controlled Partial Correlations

| metric_name | target_name | partial_spearman_rho | expected_sign_match | passes_effect_size | substantive_validity_status |
|---|---|---:|---|---|---|
| ODI_median | axis_drift_rate | 0.0221895295386 | true | false | exploratory_small_or_wrong_sign |
| AIS_median | axis_drift_rate | -0.02994388778 | true | false | exploratory_small_or_wrong_sign |
| lambda_min_clamped_median | axis_drift_rate | 0.0136075502029 | false | false | exploratory_small_or_wrong_sign |
| condition_number_median | axis_drift_rate | -0.0618899281327 | false | false | exploratory_small_or_wrong_sign |
| ODI_median | weak_drift_alignment | -0.0443781786558 | false | false | exploratory_small_or_wrong_sign |
| AIS_median | weak_drift_alignment | 0.0604530211758 | false | false | exploratory_small_or_wrong_sign |
| lambda_min_clamped_median | weak_drift_alignment | -0.0220164062011 | true | false | exploratory_small_or_wrong_sign |
| condition_number_median | weak_drift_alignment | 0.0126834753263 | true | false | exploratory_small_or_wrong_sign |

## Incremental Validity Summary

| metric_name | target_name | final_day20_status | reason |
|---|---|---|---|
| ODI_median | axis_drift_rate | exploratory_not_validated | ODI remains exploratory and is not validated for robust drift prediction. Missing: effect_size, permutation, baseline_comparison |
| AIS_median | axis_drift_rate | exploratory_not_validated | does not pass controlled Day 20 screen. Missing: effect_size, permutation, baseline_comparison |
| lambda_min_clamped_median | axis_drift_rate | exploratory_not_validated | does not pass controlled Day 20 screen. Missing: expected_sign, effect_size, permutation, baseline_comparison |
| condition_number_median | axis_drift_rate | exploratory_not_validated | does not pass controlled Day 20 screen. Missing: expected_sign, effect_size |
| ODI_median | weak_drift_alignment | exploratory_not_validated | ODI remains exploratory and is not validated for robust drift prediction. Missing: expected_sign, effect_size, baseline_comparison |
| AIS_median | weak_drift_alignment | exploratory_not_validated | does not pass controlled Day 20 screen. Missing: expected_sign, effect_size |
| lambda_min_clamped_median | weak_drift_alignment | exploratory_not_validated | does not pass controlled Day 20 screen. Missing: effect_size, permutation, baseline_comparison |
| condition_number_median | weak_drift_alignment | exploratory_not_validated | does not pass controlled Day 20 screen. Missing: effect_size, permutation, baseline_comparison |

Supported baseline candidates: `none`.

## Conclusion

Day 20 completes controlled / partial validity analysis.
Day 20 does not authorize weak-subspace update unless controlled validity passes.
Day 21 must build joint risk features using ODI + AIS + lambda_min + motion / weak-alignment evidence.
