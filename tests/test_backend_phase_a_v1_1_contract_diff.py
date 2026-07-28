from backend_phase_a_v1_1_test_support import ROOT
from zero_perturbation.backend_phase_a_v1_1 import scientific_contract_diff


def test_v1_1_changes_runner_only_and_no_scientific_contract():
    diff = scientific_contract_diff(ROOT)
    for field in (
        "scientific_parameter_difference_count",
        "scene_difference_count",
        "seed_difference_count",
        "threshold_difference_count",
        "backend_parameter_difference_count",
        "metric_difference_count",
    ):
        assert diff[field] == 0
    assert diff["runner_implementation_difference_count"] > 0
    assert diff["scientific_contract_unchanged"] is True

