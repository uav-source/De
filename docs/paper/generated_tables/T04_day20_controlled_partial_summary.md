# T04

Day20 controlled partial validity. This item supports diagnostic benchmark interpretation only; Diagnostic benchmark evidence only; do not claim substantive validity if failed.

Claim boundary: Diagnostic benchmark evidence only; do not claim substantive validity if failed.

| metric_name | target_name | passes_expected_sign | passes_effect_size | passes_permutation | passes_incremental_validity | beats_or_matches_baselines | final_day20_status | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ODI_median | axis_drift_rate | true | false | false | false | false | exploratory_not_validated | ODI remains exploratory and is not validated for robust drift prediction. Missing: effect_size, permutation, baseline_comparison |
| AIS_median | axis_drift_rate | true | false | false | false | false | exploratory_not_validated | does not pass controlled Day 20 screen. Missing: effect_size, permutation, baseline_comparison |
| lambda_min_clamped_median | axis_drift_rate | false | false | false | false | false | exploratory_not_validated | does not pass controlled Day 20 screen. Missing: expected_sign, effect_size, permutation, baseline_comparison |
| condition_number_median | axis_drift_rate | false | false | true | false | true | exploratory_not_validated | does not pass controlled Day 20 screen. Missing: expected_sign, effect_size |
| ODI_median | weak_drift_alignment | false | false | true | false | false | exploratory_not_validated | ODI remains exploratory and is not validated for robust drift prediction. Missing: expected_sign, effect_size, baseline_comparison |
| AIS_median | weak_drift_alignment | false | false | true | false | true | exploratory_not_validated | does not pass controlled Day 20 screen. Missing: expected_sign, effect_size |
| lambda_min_clamped_median | weak_drift_alignment | true | false | false | false | false | exploratory_not_validated | does not pass controlled Day 20 screen. Missing: effect_size, permutation, baseline_comparison |
| condition_number_median | weak_drift_alignment | true | false | false | false | false | exploratory_not_validated | does not pass controlled Day 20 screen. Missing: effect_size, permutation, baseline_comparison |
