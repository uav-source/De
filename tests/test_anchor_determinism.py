from anchor_audit_test_support import ROOT, sentinel_bundle
from capture_range.anchor_validity_audit import (
    load_anchor_audit_protocol,
    run_zero_registration,
)


def test_formal_zero_deterministic_recheck_meets_one_e_minus_ten():
    protocol = load_anchor_audit_protocol(ROOT)
    for method in ("full_reassociation", "frozen_jacobian"):
        row = run_zero_registration(
            sentinel_bundle(),
            method,
            13,
            protocol,
            deterministic_recheck=True,
        )
        assert row["deterministic_recheck_pass"] is True
        assert row["deterministic_recheck_translation_difference_m"] <= 1.0e-10
        assert row["deterministic_recheck_rotation_difference_rad"] <= 1.0e-10
