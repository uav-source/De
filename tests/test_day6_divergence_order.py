from fastlio2_adapter.day6_semantic_observation import classify_divergence_order


def row(*fields):
    return [
        {
            "record_index": 0,
            "scan_index": 3,
            "semantic_equal": False,
            "all_differing_fields": list(fields),
        }
    ]


def test_prior_first_classification():
    assert (
        classify_divergence_order(row("prior_position_world"))
        == "PRIOR_STATE_ALREADY_DIVERGED"
    )


def test_correspondence_first_classification():
    assert (
        classify_divergence_order(
            row("detector_pose_jacobian_rows", "accepted_index_checksum")
        )
        == "MEASUREMENT_OR_CORRESPONDENCE_DIVERGED_WITH_EQUAL_PRIOR"
    )


def test_same_record_order_is_unresolved():
    assert (
        classify_divergence_order(
            row("prior_position_world", "detector_pose_jacobian_rows")
        )
        == "SAME_RECORD_ORDER_UNRESOLVED"
    )


def test_checksum_only_can_be_insufficient():
    assert (
        classify_divergence_order(
            row("accepted_index_checksum"),
            arrays_observed=False,
        )
        == "INSUFFICIENT_RECORD_GRANULARITY"
    )
