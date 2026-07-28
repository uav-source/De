import json

from pcl_backend_v3_test_support import ARTIFACT, ROOT, file_sha256, protocol_v3


def test_v3_keeps_all_pcl_parameters_fixtures_and_truth_frozen():
    protocol = protocol_v3()
    assert protocol["immutable_backend_contract"]["required_pcl_version"] == "1.15.1"
    assert protocol["immutable_backend_contract"]["parameter_difference_from_v2_target"] == 0
    assert protocol["immutable_backend_contract"]["normal_parameter_difference_from_v2_target"] == 0
    for item in protocol["immutable_inputs"].values():
        assert file_sha256(ROOT / item["path"]) == item["sha256"]

    difference = json.loads((ARTIFACT / "parameter_diff_v2_v3.json").read_text())
    assert difference["icp_parameter_difference_count"] == 0
    assert difference["normal_parameter_difference_count"] == 0
    assert difference["fixture_difference_count"] == 0
    assert difference["truth_transform_difference_count"] == 0
    assert difference["unapproved_difference_count"] == 0
