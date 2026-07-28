from backend_qualification_test_support import qualification_decision, qualification_protocol


def test_old_capture_test_seed_firewall_and_access_count_remain_zero():
    assert qualification_protocol()["seed_firewall"][
        "old_capture_range_test_seed_access_forbidden"
    ] is True
    assert qualification_decision()["old_capture_range_test_seed_access_count"] == 0

