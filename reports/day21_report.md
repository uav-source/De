# Day 21 Report - Joint Risk Feature Analysis

## Direct Answers

- Day 21 是否完成 joint risk feature construction？Yes. It built fixed, interpretable with-ODI and no-ODI joint risk features from Day 18 windows.
- 哪个 joint risk feature 最强？`joint_risk_no_odi` for `weak_drift_alignment` by controlled/merged comparison.
- joint risk 是否优于单一指标？See `results/day30/tables/day21_joint_risk_comparison.csv`; this is decided per feature and target, not globally.
- 加入 ODI 是否优于 no-ODI joint risk？with-ODI best merged abs rho `0.120149` vs no-ODI best `0.0686899`.
- joint risk 是否通过 controlled / permutation screen？Controlled candidates: `0`; final supported joint-risk rows: `0`.
- Day 21 是否可以证明 ODI 的稳健性？No. Day 21 does not prove ODI robustness.
- Day 21 是否授权 weak-subspace update？No.
- 是否允许进入 Day 22 gate review？Yes. Day 22 must review whether any joint risk evidence is strong enough for a later method gate.

## Controlled Joint Risk Screen

| feature_name | target_name | partial_spearman_rho | permutation_p_value | controlled_validity_status |
|---|---|---:|---:|---|
| joint_risk_equal | axis_drift_rate | 0.0203752991944 | 0.308457711443 | exploratory_small_or_wrong_sign |
| joint_risk_spectral | axis_drift_rate | 0.0203752991945 | 0.258706467662 | exploratory_small_or_wrong_sign |
| joint_risk_information | axis_drift_rate | -0.00304096874715 | 0.885572139303 | exploratory_small_or_wrong_sign |
| joint_risk_odi_information | axis_drift_rate | 0.0203752991943 | 0.278606965174 | exploratory_small_or_wrong_sign |
| joint_risk_no_odi | axis_drift_rate | -0.017527626947 | 0.328358208955 | exploratory_small_or_wrong_sign |
| joint_risk_motion_aware | axis_drift_rate | -0.0164924757842 | 0.587064676617 | exploratory_small_or_wrong_sign |
| joint_risk_equal | weak_drift_alignment | 0.046535439319 | 0.233830845771 | exploratory_small_or_wrong_sign |
| joint_risk_spectral | weak_drift_alignment | 0.0465354393187 | 0.268656716418 | exploratory_small_or_wrong_sign |
| joint_risk_information | weak_drift_alignment | 0.0216267251498 | 0.358208955224 | exploratory_small_or_wrong_sign |
| joint_risk_odi_information | weak_drift_alignment | 0.0465354393182 | 0.26368159204 | exploratory_small_or_wrong_sign |
| joint_risk_no_odi | weak_drift_alignment | -0.0898048102044 | 0.124378109453 | exploratory_small_or_wrong_sign |
| joint_risk_motion_aware | weak_drift_alignment | 0.0436429361472 | 0.597014925373 | exploratory_small_or_wrong_sign |

## Joint Risk Comparison

| feature_name | target_name | merged_abs_rho | mean_within_sequence_abs_rho | controlled_abs_partial_rho | beats_single_metrics | beats_no_odi_baseline | final_day21_status |
|---|---|---:|---:|---:|---|---|---|
| joint_risk_equal | axis_drift_rate | 0.0738611703933 | 0.0621780066921 | 0.0203752991944 | false | true | exploratory_not_validated |
| joint_risk_spectral | axis_drift_rate | 0.0664864467867 | 0.0611700708885 | 0.0203752991945 | false | false | exploratory_not_validated |
| joint_risk_information | axis_drift_rate | 0.0737996326715 | 0.0481427300072 | 0.00304096874715 | false | true | exploratory_not_validated |
| joint_risk_odi_information | axis_drift_rate | 0.0804736394053 | 0.07503138685 | 0.0203752991943 | false | true | exploratory_not_validated |
| joint_risk_no_odi | axis_drift_rate | 0.0686898788293 | 0.0421122740949 | 0.017527626947 | false | true | exploratory_not_validated |
| joint_risk_motion_aware | axis_drift_rate | 0.0712767129717 | 0.0440375784703 | 0.0164924757842 | false | true | exploratory_not_validated |
| joint_risk_equal | weak_drift_alignment | 0.0911629934282 | 0.0474627919145 | 0.046535439319 | false | true | exploratory_not_validated |
| joint_risk_spectral | weak_drift_alignment | 0.051736727616 | 0.0473084950992 | 0.0465354393187 | false | true | exploratory_not_validated |
| joint_risk_information | weak_drift_alignment | 0.111834197783 | 0.0495600925436 | 0.0216267251498 | false | true | exploratory_not_validated |
| joint_risk_odi_information | weak_drift_alignment | 0.120149086961 | 0.0629929918808 | 0.0465354393182 | false | true | exploratory_not_validated |
| joint_risk_no_odi | weak_drift_alignment | 0.00315586978802 | 0.0538652491225 | 0.0898048102044 | false | true | exploratory_not_validated |
| joint_risk_motion_aware | weak_drift_alignment | 0.0203360306457 | 0.0533231088437 | 0.0436429361472 | false | true | exploratory_not_validated |

## Conclusion

Day 21 builds and screens interpretable joint risk features.
Day 21 does not prove ODI robustness.
Weak-subspace update is not authorized unless a joint risk feature passes strict controlled validity.
Day 22 must perform a go/no-go gate review before any method update is implemented.
