from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np

from capture_range.day2_development_protocol import (
    DevelopmentSeedFirewall,
    load_day2_development_protocol,
)
from capture_range.day2_development_scene import (
    build_development_base_snapshot,
    build_scene_geometry,
)

ROOT = Path(__file__).resolve().parents[1]


def _sentinel_firewall(protocol):
    return DevelopmentSeedFirewall(
        global_seed=7,
        allowed_geometry_seeds=(17,),
        allowed_measurement_seeds=(23,),
        repeats=1,
        forbidden_geometry_seed_sentinels=(29,),
        forbidden_measurement_seed_sentinels=(31,),
        scene_variants=tuple(protocol.section("scene_generation")["variants_in_order"]),
        stream_roles=tuple(protocol.section("measurement_realization")["stream_roles_in_order"]),
    )


def test_all_seven_scene_variants_generate_with_sentinel_seed():
    protocol = load_day2_development_protocol(ROOT)
    firewall = _sentinel_firewall(protocol)
    rows = []
    for scene in protocol.section("scene_generation")["variants_in_order"]:
        geometry = build_scene_geometry(protocol, firewall, scene, 17, 23, 0, "map")
        assert geometry.points_world.shape[0] > 1000
        assert geometry.points_world.shape == geometry.normals_world.shape
        assert np.all(np.isfinite(geometry.points_world))
        assert len(geometry.point_checksum) == 64
        rows.append(scene)
    assert len(rows) == 7


def test_base_snapshot_is_deterministic_and_contains_only_scalar_metadata():
    protocol = load_day2_development_protocol(ROOT)
    left = build_development_base_snapshot(protocol, _sentinel_firewall(protocol), "LONG_CORRIDOR", 17, 23, 0)
    right = build_development_base_snapshot(protocol, _sentinel_firewall(protocol), "LONG_CORRIDOR", 17, 23, 0)
    for field in ("base_snapshot_checksum", "scan_checksum", "map_checksum", "dropout_checksum"):
        assert getattr(left, field) == getattr(right, field)
    assert np.array_equal(left.snapshot.scan_points, right.snapshot.scan_points)
    assert np.array_equal(left.snapshot.local_map_points, right.snapshot.local_map_points)
    assert all(not isinstance(value, np.ndarray) for value in left.snapshot.metadata.values())
    text = repr((left.snapshot.metadata, left.snapshot.registration_config)).lower()
    assert "theoretical" not in text
    assert "direction_role" not in text


def test_snapshot_bundle_has_the_frozen_checksum_contract():
    protocol = load_day2_development_protocol(ROOT)
    bundle = build_development_base_snapshot(protocol, _sentinel_firewall(protocol), "END_FACE_TRANSITION_WEAK", 17, 23, 0)
    required = set(protocol.section("snapshot_contract")["required_checksums"])
    assert required <= {field.name for field in dataclasses.fields(bundle)}
    assert bundle.scan_point_count < bundle.scan_point_count_before_dropout
    assert bundle.map_point_count == bundle.map_point_count_before_dropout
