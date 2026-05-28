# T06

Day22 gate decision. This item supports diagnostic benchmark interpretation only; Diagnostic benchmark evidence only; do not claim Go method result.

Claim boundary: Diagnostic benchmark evidence only; do not claim Go method result.

| gate_name | requirement | observed | passed | decision_impact | reason |
| --- | --- | --- | --- | --- | --- |
| unbiased_protocol_gate | Day16 axis_bias_mode=none and applied_axis_bias all zero | True | true | blocks biased protocol claims if false | unbiased protocol established |
| within_sequence_validation_gate | Day18 window validation completed | True | true | blocks Day19+ inference if false | Day18 manifest OK with nonempty windows |
| grouped_loso_gate | Day19 grouped / LOSO completed | True | true | blocks generalization claims if false | Day19 manifest OK |
| odi_controlled_validity_gate | ODI candidate_supported in Day20 controlled validity | exploratory_not_validated | false | blocks single-ODI validity claims | ODI remains exploratory and is not validated for robust drift prediction. Missing: effect_size, permutation, baseline_comparison |
| joint_risk_candidate_gate | At least one Day21 joint risk candidate_supported | False | false | blocks method update if false | no Day21 joint risk candidate passed |
| weak_update_authorization_gate | Day21 manifest weak_update_authorized true | False | false | directly controls method update authorization | Day21 did not authorize weak update |
| method_update_gate | joint_risk_candidate_gate and weak_update_authorization_gate pass | False | false | final method update go/no-go | method update blocked by Day22 gate |
