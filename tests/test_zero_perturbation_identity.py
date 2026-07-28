import numpy as np

from anchor_audit_test_support import ROOT, sentinel_bundle
from capture_range.anchor_validity_audit import (
    load_anchor_audit_protocol,
    pose_from_json,
    run_zero_registration,
)


def test_zero_registration_starts_at_exact_reference_for_both_methods():
    bundle = sentinel_bundle()
    protocol = load_anchor_audit_protocol(ROOT)
    for method in ("full_reassociation", "frozen_jacobian"):
        row = run_zero_registration(
            bundle,
            method,
            7,
            protocol,
            deterministic_recheck=True,
        )
        np.testing.assert_array_equal(
            pose_from_json(row["reference_pose"]),
            pose_from_json(row["zero_initial_pose"]),
        )
        assert row["signed_amplitude"] == 0.0
        assert row["zero_success_under_current_gt_rule"] is True
        assert row["zero_translation_shift_from_reference_m"] <= 0.02
        assert row["zero_rotation_shift_from_reference_rad"] <= np.deg2rad(0.5)
