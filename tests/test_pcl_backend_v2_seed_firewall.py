from pcl_backend_v2_test_support import ROOT, protocol_v2


def test_v2_fixture_generator_has_no_rng_or_seed_schedule_access():
    source = (ROOT / "tests/data/pcl_backend_v2/generate_fixtures.py").read_text()
    forbidden = ("np.random", "random.", "seed_schedule", "confirmatory", "geometry_seed")
    assert not any(value in source for value in forbidden)
    firewall = protocol_v2()["seed_firewall"]
    assert firewall["fixture_generator_random_seed_used"] is False
    assert firewall["target_access_count"] == 0
