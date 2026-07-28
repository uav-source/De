from pcl_backend_v2_test_support import ROOT, file_sha256, protocol_v2


def test_v2_preserves_v1_failure_and_freezes_the_original_pcl_parameters():
    protocol = protocol_v2()
    preserved = protocol["v1_preserved_result"]
    assert preserved["PCL_DEPENDENCY_READY"] is True
    assert preserved["PCL_CLI_COMPILED"] is True
    assert preserved["PCL_V1_PLANAR_IDENTITY_SMOKE"] == "FAIL"
    assert preserved["reclassification"] == {
        "PCL_V1_SMOKE_FIXTURE_DEGENERATE": True,
        "PCL_BACKEND_QUALIFICATION": "NOT_EVALUATED",
        "point_cloud_rank": 2,
        "point_to_plane_jacobian_rank": 3,
        "point_to_plane_hessian_eigenvalues": [0.0, 0.0, 0.0, 3.36, 3.36, 64.0],
        "interpretation": "fixture_is_not_a_valid_hard_gate_for_six_dof_backend_qualification",
    }
    contract = protocol["immutable_backend_contract"]
    assert contract["required_pcl_version"] == "1.15.1"
    assert contract["normal_estimation"] == {
        "implementation": "pcl::NormalEstimationOMP",
        "method": "KSearch",
        "k": 50,
        "threads": 1,
    }
    assert contract["icp"] == {
        "maximum_correspondence_distance_m": 0.50,
        "maximum_iterations": 50,
        "transformation_epsilon": 1.0e-10,
        "euclidean_fitness_epsilon": 1.0e-10,
        "use_reciprocal_correspondences": False,
        "use_symmetric_objective": False,
        "enforce_same_direction_normals": True,
    }


def test_every_v2_input_and_the_unchanged_v1_fixture_match_the_protocol_hashes():
    lock = protocol_v2()["fixture_lock"]
    for name, value in lock.items():
        if not isinstance(value, dict) or "path" not in value:
            continue
        assert file_sha256(ROOT / value["path"]) == value["sha256"], name
