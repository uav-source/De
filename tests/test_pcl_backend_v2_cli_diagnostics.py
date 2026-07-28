from pcl_backend_v2_test_support import ROOT, protocol_v2


def test_v2_cli_exposes_separate_diagnostics_and_reason_vocabulary():
    source = (ROOT / "tools/pcl_point_to_plane/pcl_point_to_plane_cli.cpp").read_text()
    required = protocol_v2()["cli_diagnostics"]["required_scalar_fields"]
    for field in required:
        assert f'"{field}"' in source
    for cloud in ("source", "target"):
        for field in protocol_v2()["cli_diagnostics"][
            "source_and_target_normal_fields"
        ]:
            assert f'{cloud}_normal_{field}' in source or (
                'add_normal_statistics(output, "' + cloud + '"' in source
                and f'"_normal_{field}"' in source
            )
    for reason in protocol_v2()["cli_diagnostics"]["failure_reason_vocabulary"]:
        assert f'"{reason}"' in source
    assert "pcl_icp_did_not_converge_or_nonfinite" not in source


def test_v2_cli_keeps_every_frozen_pcl_parameter_assignment():
    source = (ROOT / "tools/pcl_point_to_plane/pcl_point_to_plane_cli.cpp").read_text()
    expected = (
        "estimator.setNumberOfThreads(1);",
        "estimator.setKSearch(kNormalNeighbors);",
        "icp.setMaxCorrespondenceDistance(kMaximumCorrespondenceDistanceM);",
        "icp.setMaximumIterations(kMaximumIterations);",
        "icp.setTransformationEpsilon(kTransformationEpsilon);",
        "icp.setEuclideanFitnessEpsilon(kEuclideanFitnessEpsilon);",
        "icp.setUseReciprocalCorrespondences(false);",
        "icp.setUseSymmetricObjective(false);",
        "icp.setEnforceSameDirectionNormals(true);",
    )
    assert all(value in source for value in expected)


def test_v2_truth_is_owned_by_the_verifier_and_never_passed_to_cli():
    cmake = (ROOT / "tools/pcl_point_to_plane/CMakeLists.txt").read_text()
    verifier = (
        ROOT / "tools/pcl_point_to_plane/verify_pcl_backend_v2.py"
    ).read_text()
    assert "--truth" in cmake
    assert 'command = [str(args.cli.resolve()), "--config", str(args.config.resolve())]' in verifier
    assert "args.truth" not in verifier.split("command =", 1)[1].split("subprocess.run", 1)[0]
