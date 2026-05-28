# T02

Day18 within-sequence validation results. This item supports diagnostic benchmark interpretation only; Diagnostic benchmark evidence only; do not claim robust prediction.

Claim boundary: Diagnostic benchmark evidence only; do not claim robust prediction.

| sequence_id | scene_family | n_trials | n_windows | n_valid_correlations | best_metric_for_axis_drift | best_abs_rho_for_axis_drift | ODI_axis_drift_rho | AIS_axis_drift_rho | lambda_min_clamped_axis_drift_rho | condition_number_axis_drift_rho | interpretation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OC-L0-S01-M1 | OC | 20 | 740 | 8 | ODI_median | 0.227916791073 | -0.227916791073 | 0.172531392814 | -0.0160667576162 | 0.0133060567464 | ODI is strongest for axis drift in this sequence only; not a cross-sequence claim |
| ST-L3-S01-M1 | ST | 20 | 900 | 12 | ODI_median | 0.0878434540112 | -0.0878434540112 | 0.0399336541898 | 0.00852981040715 | -0.0772537388783 | ODI is strongest for axis drift in this sequence only; not a cross-sequence claim |
| CT-L2-S01-M2 | CT | 20 | 820 | 12 | lambda_min_clamped_median | 0.02296580028 | 0.0215333604313 | -0.0199496458027 | 0.02296580028 | -0.0158025059429 | lambda_min_clamped_median is strongest for axis drift in this sequence; ODI is not uniquely supported |
| RT-L4-S01-M1 | RT | 20 | 980 | 9 | condition_number_median | 0.0796400157518 | -0.061451576363 | 0.0434276654697 | nan | -0.0796400157518 | condition_number_median is strongest for axis drift in this sequence; ODI is not uniquely supported |
