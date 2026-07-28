from backend_qualification_test_support import qualification_decision


def test_redesign_authorization_conjunction_fails_at_build_smoke():
    decision = qualification_decision()
    prerequisites = (
        "PCL_DEPENDENCY_READY",
        "PCL_BACKEND_BUILD_PASS",
        "OPEN3D_BACKEND_QUALIFICATION_PASS",
        "PCL_BACKEND_QUALIFICATION_PASS",
        "IDEAL_MATCHED_SNAPSHOT_DIVERSITY_PASS",
        "BACKEND_INPUT_PAIRING_PASS",
        "TWO_INDEPENDENT_BACKENDS_QUALIFIED",
        "CROSS_BACKEND_SCENE_SIGNAL_OBSERVED",
    )
    expected = all(decision[name] is True for name in prerequisites)
    assert expected is False
    assert decision["ZERO_PERTURBATION_FULL_DEVELOPMENT_REDESIGN_AUTHORIZED"] is expected
    assert decision["ZERO_PERTURBATION_FULL_DEVELOPMENT_RUN_AUTHORIZED"] is False

