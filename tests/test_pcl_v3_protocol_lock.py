from pcl_backend_v3_test_support import ROOT, file_sha256, protocol_v3


def test_v3_scope_and_v2_failure_are_prospectively_frozen():
    protocol = protocol_v3()
    assert protocol["protocol"]["protocol_type"] == "rotation_metric_validity_requalification"
    assert protocol["protocol"]["phase_a_authorized_before_run"] is False
    assert protocol["protocol"]["phase_b_authorized"] is False
    assert protocol["protocol"]["allowed_microtests_only"] == [
        "NONDEGENERATE_IDENTITY",
        "KNOWN_SMALL_TRANSFORM",
        "PLANAR_DEGENERACY_DIAGNOSTIC",
    ]
    preserved = protocol["v2_archive"]["preserved_decision"]
    assert preserved == {
        "test_a": "PASS",
        "test_b": "FAIL",
        "test_c": "PASS",
        "PCL_BACKEND_IMPLEMENTATION_VALID": False,
        "PCL_BACKEND_PHASE_A_QUALIFICATION_AUTHORIZED": False,
    }


def test_v3_reuses_every_v2_fixture_config_and_truth_hash():
    for name, item in protocol_v3()["immutable_inputs"].items():
        assert file_sha256(ROOT / item["path"]) == item["sha256"], name


def test_v3_thresholds_and_reflection_safe_projection_are_locked():
    protocol = protocol_v3()
    assert protocol["microtests"]["NONDEGENERATE_IDENTITY"]["gates"][
        "rotation_update_norm_rad_max"
    ] == 1.0e-8
    assert protocol["microtests"]["KNOWN_SMALL_TRANSFORM"]["gates"][
        "projected_atan2_rotation_error_to_truth_rad_max"
    ] == 1.0e-4
    projection = protocol["nearest_so3_projection"]["reflection_handling"]
    assert projection["D"] == "diag(1, 1, sign(det(U * V_transpose)))"
    assert projection["require_projected_determinant_positive"] is True
