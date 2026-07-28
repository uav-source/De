from anchor_audit_test_support import ROOT
from capture_range.anchor_validity_audit import (
    classify_d50_zero_root_cause,
    load_anchor_audit_protocol,
)


def test_root_cause_has_one_primary_and_ordered_secondary_reasons():
    protocol = load_anchor_audit_protocol(ROOT)
    primary, secondary = classify_d50_zero_root_cause(
        {
            "MULTIPLE_ATTRACTORS": True,
            "ZERO_SOLVER_FAILURE": True,
            "REFERENCE_NOT_FIXED_POINT": True,
        },
        protocol,
    )
    assert primary == "MULTIPLE_ATTRACTORS"
    assert secondary == ("ZERO_SOLVER_FAILURE", "REFERENCE_NOT_FIXED_POINT")
    assert classify_d50_zero_root_cause({}, protocol) == ("UNKNOWN", ())
