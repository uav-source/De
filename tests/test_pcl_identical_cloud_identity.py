from backend_qualification_test_support import ROOT, qualification_decision


def test_identical_cloud_failure_is_retained_as_terminal_build_evidence():
    smoke = (
        ROOT / "reports/zero_perturbation_pcl_environment/smoke_test.txt"
    ).read_text()
    assert '"has_converged":false' in smoke
    assert '"finite_output":false' in smoke
    decision = qualification_decision()
    assert decision["PCL_CLI_IDENTITY_SMOKE_PASS"] is False
    assert decision["parameter_rescue_attempted"] is False

