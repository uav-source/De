from eval.weak_update_stage2c import stage2c_authorizations


def test_authorization_requires_complete_projected_gain_pass():
    failed = stage2c_authorizations({"PROJECTED_GAIN_UPDATE": "PROJECTED_GAIN_UPDATE_FAIL"})
    assert failed == {
        "PROJECTED_GAIN_UPDATE_PASS": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "RISK_WARNING_AUTHORIZED": False,
    }
    passed = stage2c_authorizations({"PROJECTED_GAIN_UPDATE": "PROJECTED_GAIN_UPDATE_PASS"})
    assert passed["PROJECTED_GAIN_UPDATE_PASS"] is True
    assert passed["FAST_LIO2_INTEGRATION_AUTHORIZED"] is True
    assert passed["RISK_WARNING_AUTHORIZED"] is False
