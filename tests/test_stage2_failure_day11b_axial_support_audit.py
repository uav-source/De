import numpy as np

from eval.stage2_failure_day11b_provenance import audit_axial_support


def _records():
    return [{"frame_index": 1}, {"frame_index": 2}]


def _observations():
    return {
        "is_axial_support": np.array([
            [True, False, False], [True, True, False], [True, False, False]
        ]),
        "contamination_mask": np.array([
            [False, False, False], [True, False, False], [True, False, False]
        ]),
    }


def test_mask_derived_axial_only_audit_passes_for_coherent_stress():
    rows, summary = audit_axial_support(
        "case", "coherent_subhuber_slip", _records(), _observations()
    )
    assert summary["pass"] is True
    assert summary["contaminated_measurement_count"] == 2
    assert summary["contaminated_axial_support_count"] == 2
    assert all(row["axial_only_frame_pass"] for row in rows)


def test_contamination_on_non_axial_support_fails():
    observations = _observations()
    observations["contamination_mask"][1, 2] = True
    _, summary = audit_axial_support(
        "case", "coherent_subhuber_slip", _records(), observations
    )
    assert summary["pass"] is False
    assert summary["contaminated_non_axial_support_count"] == 1


def test_stress_name_alone_cannot_make_zero_contamination_pass():
    observations = _observations()
    observations["contamination_mask"][:] = False
    _, summary = audit_axial_support(
        "case", "coherent_subhuber_slip", _records(), observations
    )
    assert summary["pass"] is False


def test_clean_case_with_contamination_fails():
    _, summary = audit_axial_support("case", "clean", _records(), _observations())
    assert summary["pass"] is False
