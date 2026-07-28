import csv

from anchor_audit_test_support import ROOT
from capture_range.anchor_validity_audit import (
    EXPECTED_CONDITIONS,
    build_anchor_condition_snapshots,
    load_anchor_audit_protocol,
    noise_conditions,
)
from capture_range.day2_development_protocol import (
    development_seed_firewall,
    load_day2_development_protocol,
)


def test_noise_ablation_has_exactly_four_predeclared_conditions_and_no_fifth():
    protocol = load_anchor_audit_protocol(ROOT)
    conditions = noise_conditions(protocol)
    assert tuple(
        (
            value.condition_id,
            value.scan_noise_sigma_m,
            value.map_noise_sigma_m,
            value.scan_dropout_fraction,
        )
        for value in conditions
    ) == EXPECTED_CONDITIONS
    assert all(value.map_dropout_fraction == 0.0 for value in conditions)
    assert protocol.section("noise_ablation")["dropout_causal_contrast_available"] is False


def test_locked_full_noise_reproduces_archived_development_snapshot_checksums():
    protocol = load_anchor_audit_protocol(ROOT)
    development = load_day2_development_protocol(ROOT)
    firewall = development_seed_firewall(development)
    bundles = build_anchor_condition_snapshots(
        development,
        protocol,
        firewall,
        "LONG_CORRIDOR",
        1101,
        2101,
        0,
    )
    locked = next(row for row in bundles if row.condition_id == "LOCKED_FULL_NOISE")
    inventory = (
        ROOT
        / "artifacts/history/directional_capture_range_day2_development_pre_anchor_audit/snapshot_inventory.csv"
    )
    with inventory.open(encoding="utf-8", newline="") as stream:
        archived = next(
            row
            for row in csv.DictReader(stream)
            if row["base_snapshot_id"] == locked.base_snapshot_id
        )
    for name in (
        "base_snapshot_checksum",
        "scan_checksum",
        "map_checksum",
        "dropout_checksum",
    ):
        assert getattr(locked, name) == archived[name]
