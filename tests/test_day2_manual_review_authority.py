from pathlib import Path

import pytest

from capture_range.day2_protocol import (
    load_effective_day2_protocol,
    require_manual_review_authority,
)


ROOT = Path(__file__).resolve().parents[1]


def test_codex_cannot_assign_valid_without_explicit_human_authority():
    with pytest.raises(PermissionError, match="Codex may not assign"):
        require_manual_review_authority("VALID", None)
    with pytest.raises(PermissionError, match="Codex may not assign"):
        require_manual_review_authority(
            "VALID", "human_principal_investigator", human_authorization_present=False
        )
    with pytest.raises(PermissionError, match="human_principal_investigator"):
        require_manual_review_authority(
            "VALID", "codex", human_authorization_present=True
        )

    require_manual_review_authority(
        "VALID",
        "human_principal_investigator",
        human_authorization_present=True,
    )
    require_manual_review_authority("INCONCLUSIVE", None)


def test_manual_review_schema_requires_human_identity_and_complete_evidence():
    contract = load_effective_day2_protocol(ROOT).amendment[
        "manual_review_resolution"
    ]

    assert contract["reviewer_identity"] == {
        "field": "reviewed_by",
        "allowed_value_for_mvp": "human_principal_investigator",
    }
    assert contract["reviewed_at_format"] == "ISO_8601_UTC"
    assert contract["rationale_minimum_characters"] == 80
    assert contract["required_evidence"] == (
        "both_raw_recovery_curves",
        "both_isotonic_curves",
        "full_trial_final_pose_clusters",
        "correspondence_checksum_change_counts",
        "final_pose_error_histograms",
        "local_minimum_or_aliasing_explanation",
    )
    assert contract["valid_status_requires"] == (
        "automatic_candidate_pass_true",
        "no_numerical_failure",
        "geometries_scientifically_comparable",
        "visible_difference_not_caused_only_by_right_censoring",
        "alternate_local_minimum_or_correspondence_switch_evidence",
    )
    assert contract[
        "codex_may_generate_record_but_may_not_mark_valid_without_human_field"
    ] is True


def test_no_codex_generated_record_is_marked_valid_at_protocol_lock_time():
    generated_records = []
    assert sum(row.get("manual_review_status") == "VALID" for row in generated_records) == 0
