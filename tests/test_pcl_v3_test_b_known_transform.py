import json

from pcl_backend_v3_test_support import ARTIFACT


def test_v3_known_small_transform_uses_projected_atan2_and_passes_frozen_gates():
    result = json.loads((ARTIFACT / "test_b_result.json").read_text())
    assert result["microtest"] == "KNOWN_SMALL_TRANSFORM"
    assert result["truth_passed_to_cli"] is False
    assert result["truth_argument_passed_to_registration_cli"] is False
    assert result["microtest_pass"] is True
    assert result["translation_error_to_truth_m"] <= 1.0e-4
    assert result["rotation_error_to_truth_rad"] <= 1.0e-4
    assert result["ROTATION_MATRIX_QUALITY_PASS"] is True
    assert result["ROTATION_METRIC_CROSSCHECK_PASS"] is True
