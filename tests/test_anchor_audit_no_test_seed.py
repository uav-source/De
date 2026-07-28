from anchor_audit_test_support import ROOT
from capture_range.anchor_validity_audit import load_anchor_audit_protocol
from capture_range.day2_development_protocol import load_day2_development_protocol


def test_anchor_audit_seed_inventory_is_exact_development_subset_only():
    audit = load_anchor_audit_protocol(ROOT)
    development = load_day2_development_protocol(ROOT)
    audit_seed = audit.section("seed_authority")
    development_seed = development.section("seed_firewall")
    assert tuple(audit_seed["allowed_geometry_seeds"]) == tuple(
        development_seed["allowed_geometry_seeds"]
    )
    assert tuple(audit_seed["allowed_measurement_seeds"]) == tuple(
        development_seed["allowed_measurement_seeds"]
    )
    assert audit_seed["parse_confirmatory_seed_split"] is False
    assert "forbidden_confirmatory_geometry_seed_sentinels" not in audit_seed
    assert "forbidden_confirmatory_measurement_seed_sentinels" not in audit_seed
