from backend_qualification_test_support import qualification_decision, qualification_protocol


def test_confirmatory_seed_firewall_and_access_count_remain_zero():
    assert qualification_protocol()["seed_firewall"][
        "confirmatory_seed_instantiation_forbidden"
    ] is True
    assert qualification_decision()["confirmatory_seed_instantiation_count"] == 0

