"""Cached Development protocol/snapshot helpers for contract tests."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from zero_perturbation.protocol import DevelopmentSeedFirewall, load_protocol
from zero_perturbation.snapshot_builder import build_snapshot
from zero_perturbation.types import SnapshotKey


ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def development_protocol():
    return load_protocol(ROOT)


@lru_cache(maxsize=None)
def development_snapshot(condition: str):
    protocol = development_protocol()
    firewall = DevelopmentSeedFirewall(protocol)
    geometry = next(iter(protocol.development_seeds["geometry"].values()))
    measurement = next(iter(protocol.development_seeds["measurement"].values()))
    return build_snapshot(
        protocol,
        firewall,
        SnapshotKey("GEOMETRY_RICH_ROOM", geometry, measurement, 0, condition),
    )
