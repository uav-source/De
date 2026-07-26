import inspect

import pytest

import capture_range.day2_development_protocol as development_protocol
from capture_range.day2_development_protocol import (
    DevelopmentSeedAccessError,
    DevelopmentSeedFirewall,
)


def sentinel_firewall():
    return DevelopmentSeedFirewall(
        global_seed=900_001,
        allowed_geometry_seeds=(900_101,),
        allowed_measurement_seeds=(900_201,),
        repeats=2,
        forbidden_geometry_seed_sentinels=(900_301,),
        forbidden_measurement_seed_sentinels=(900_401,),
        scene_variants=("SYNTHETIC_SENTINEL",),
        stream_roles=("sentinel_noise",),
    )


def test_sentinel_development_access_is_guarded_before_materialization():
    firewall = sentinel_firewall()

    assert firewall.assert_geometry_allowed(900_101) == 900_101
    assert firewall.assert_allowed(900_101, 900_201) == (900_101, 900_201)
    assert isinstance(
        firewall.stream_seed(
            "SYNTHETIC_SENTINEL", 900_101, 900_201, 1, "sentinel_noise"
        ),
        int,
    )
    firewall.rng("SYNTHETIC_SENTINEL", 900_101, 900_201, 0, "sentinel_noise")

    counts = firewall.audit_counts
    assert counts["confirmatory_seed_access_attempt_count"] == 0
    assert counts["confirmatory_seed_materialization_count"] == 0
    assert counts["seed_hash_materialization_count"] == 2
    assert counts["rng_materialization_count"] == 1


@pytest.mark.parametrize(
    ("geometry_seed", "measurement_seed", "message"),
    [
        (900_301, 900_201, "confirmatory geometry"),
        (900_101, 900_401, "confirmatory measurement"),
        (900_999, 900_201, "unknown Development geometry"),
        (900_101, 900_999, "unknown Development measurement"),
    ],
)
def test_rejected_seed_never_reaches_hash_or_rng(
    monkeypatch, geometry_seed, measurement_seed, message
):
    firewall = sentinel_firewall()
    calls = {"hash": 0, "pcg64": 0}

    def forbidden_hash(_payload):
        calls["hash"] += 1
        raise AssertionError("hash must not be reached")

    def forbidden_pcg64(_seed):
        calls["pcg64"] += 1
        raise AssertionError("RNG must not be reached")

    monkeypatch.setattr(development_protocol, "canonical_seed", forbidden_hash)
    monkeypatch.setattr(development_protocol.np.random, "PCG64", forbidden_pcg64)

    with pytest.raises(DevelopmentSeedAccessError, match=message):
        firewall.rng(
            "SYNTHETIC_SENTINEL",
            geometry_seed,
            measurement_seed,
            0,
            "sentinel_noise",
        )
    assert calls == {"hash": 0, "pcg64": 0}
    assert firewall.audit_counts["seed_hash_materialization_count"] == 0
    assert firewall.audit_counts["rng_materialization_count"] == 0


def test_point_cloud_stream_api_excludes_direction_amplitude_and_method():
    assert tuple(inspect.signature(DevelopmentSeedFirewall.stream_seed).parameters) == (
        "self",
        "scene_variant",
        "geometry_seed",
        "measurement_seed",
        "repeat_index",
        "stream_role",
    )
