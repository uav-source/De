import json

from pcl_backend_v3_test_support import ARTIFACT


def test_v3_planar_fixture_remains_a_rank_deficiency_diagnostic():
    result = json.loads((ARTIFACT / "test_c_result.json").read_text())
    payload = result["cli_result"]
    assert result["microtest"] == "PLANAR_DEGENERACY_DIAGNOSTIC"
    assert result["microtest_pass"] is True
    assert payload["point_cloud_rank"] == 2
    assert payload["point_to_plane_jacobian_rank"] < 6
    assert payload["rank_deficient"] is True
    assert payload["failure_reason"] == "RANK_DEFICIENT_DIAGNOSTIC"
