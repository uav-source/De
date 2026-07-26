import pytest

from fastlio2_adapter.day6_semantic_observation import (
    Day6SemanticError,
    evidence_granularity_matrix,
    validate_checksum_only_claim,
)


def test_missing_payload_and_map_evidence_cannot_prove_identity():
    rows = {
        row["evidence"]: row
        for row in evidence_granularity_matrix(
            {
                "accepted_index_checksum": 1,
                "formal_correspondence_checksum": 2,
            }
        )
    }
    assert rows["raw_lidar_payload_checksum"]["status"] == "NOT_RECORDED"
    assert rows["raw_imu_bundle_checksum"]["status"] == "NOT_RECORDED"
    assert rows["map_content_checksum"]["status"] == "NOT_RECORDED"
    assert rows["full_accepted_index_array"]["status"] == "CHECKSUM_ONLY"
    assert rows["full_plane_parameter_array"]["status"] == "CHECKSUM_ONLY"


def test_checksum_only_rejects_array_element_claim():
    with pytest.raises(Day6SemanticError, match="array-element"):
        validate_checksum_only_claim("CHECKSUM_ONLY", "ARRAY_ELEMENT_IDENTITY")
