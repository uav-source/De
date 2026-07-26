from fastlio2_adapter.day6_semantic_observation import (
    first_divergence_by_field,
    first_semantic_divergence,
    previous_record_semantic_identity,
)


def rows():
    return [
        {
            "record_index": 0,
            "scan_index": 3,
            "semantic_equal": True,
            "all_differing_fields": [],
        },
        {
            "record_index": 1,
            "scan_index": 4,
            "semantic_equal": True,
            "all_differing_fields": [],
        },
        {
            "record_index": 2,
            "scan_index": 5,
            "semantic_equal": False,
            "all_differing_fields": [
                "valid_correspondence_count",
                "detector_pose_jacobian_rows",
            ],
        },
    ]


def test_first_divergence_and_previous_record_are_localized():
    assert first_semantic_divergence(rows()) == {
        "record_index": 2,
        "scan_index": 5,
    }
    assert previous_record_semantic_identity(rows()) == "CONFIRMED"
    by_field = first_divergence_by_field(rows())
    assert by_field["valid_correspondence_count"] == {
        "record_index": 2,
        "scan_index": 5,
    }
    assert by_field["prior_position_world"] is None


def test_first_record_divergence_has_no_previous_record():
    value = [dict(rows()[2], record_index=0, scan_index=3)]
    assert (
        previous_record_semantic_identity(value)
        == "NOT_OBSERVABLE_NO_PREVIOUS_RECORD"
    )
