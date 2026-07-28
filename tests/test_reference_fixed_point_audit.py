from anchor_audit_test_support import ROOT, sentinel_bundle
from capture_range.anchor_validity_audit import (
    load_anchor_audit_protocol,
    run_zero_registration,
)


def test_perfect_planar_reference_has_zero_gradient_and_no_fixed_point_rejection():
    row = run_zero_registration(
        sentinel_bundle(),
        "full_reassociation",
        11,
        load_anchor_audit_protocol(ROOT),
        deterministic_recheck=True,
    )
    assert row["zero_gradient_norm_at_reference"] <= 1.0e-12
    assert row["zero_first_step_translation_m"] <= 1.0e-12
    assert row["zero_first_step_rotation_rad"] <= 1.0e-12
    assert row["reference_pose_not_registration_fixed_point"] is False
