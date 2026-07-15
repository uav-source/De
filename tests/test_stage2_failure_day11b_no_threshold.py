from eval.stage2_failure_day11b_schema import evaluate_day11b_gate
from test_stage2_failure_day11b_gate_logic import passing_values


def test_threshold_and_classification_outputs_cannot_pass_gate():
    for field in ("threshold_created", "auroc_computed", "fpr_computed", "f1_computed", "detection_delay_computed"):
        values = passing_values()
        values[field] = True
        assert evaluate_day11b_gate(values) is False


def test_figures_directory_flag_cannot_pass_gate():
    values = passing_values()
    values["figures_generated"] = True
    assert evaluate_day11b_gate(values) is False
