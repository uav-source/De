import json

from pcl_backend_v3_test_support import ARTIFACT


def test_v3_nondegenerate_identity_passes_every_frozen_gate():
    result = json.loads((ARTIFACT / "test_a_result.json").read_text())
    assert result["microtest"] == "NONDEGENERATE_IDENTITY"
    assert result["microtest_pass"] is True
    assert result["ROTATION_MATRIX_QUALITY_PASS"] is True
    assert result["ROTATION_METRIC_CROSSCHECK_PASS"] is True
    assert result["formal_rotation_error_rad"] <= 1.0e-8
    assert result["cli_result"]["translation_update_norm_m"] <= 1.0e-8
