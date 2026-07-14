from eval.weak_update_stage2b import stage2b_authorizations


def test_authorization_requires_complete_selective_update_pass():
    failed = stage2b_authorizations({"selective_update": "SELECTIVE_UPDATE_FAIL"})
    assert failed == {
        "SELECTIVE_UPDATE_PASS": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "RISK_WARNING_AUTHORIZED": False,
    }
    passed = stage2b_authorizations({"selective_update": "SELECTIVE_UPDATE_PASS"})
    assert passed["SELECTIVE_UPDATE_PASS"] is True
    assert passed["FAST_LIO2_INTEGRATION_AUTHORIZED"] is True
    assert passed["RISK_WARNING_AUTHORIZED"] is False

