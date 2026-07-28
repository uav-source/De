from zero_perturbation.protocol import DevelopmentSeedFirewall
from zero_perturbation.snapshot_builder import build_snapshot
from zero_perturbation_test_support import development_protocol
from zero_perturbation.types import SnapshotKey


def test_snapshot_randomness_has_no_method_dimension():
    protocol = development_protocol()
    geometry = next(iter(protocol.development_seeds["geometry"].values()))
    measurement = next(iter(protocol.development_seeds["measurement"].values()))
    key = SnapshotKey("GEOMETRY_RICH_ROOM", geometry, measurement, 0, "FULL_NOISE")
    first = build_snapshot(protocol, DevelopmentSeedFirewall(protocol), key)
    second = build_snapshot(protocol, DevelopmentSeedFirewall(protocol), key)
    assert first.checksums == second.checksums
