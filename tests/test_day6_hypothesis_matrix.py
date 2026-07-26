import pytest

from fastlio2_adapter.day6_divergence_hypotheses import (
    Day6HypothesisError,
    HYPOTHESIS_IDS,
    build_hypothesis_rows,
    validate_hypothesis_rows,
)


def test_fixed_hypothesis_matrix_is_complete_and_bounded():
    rows = build_hypothesis_rows({})
    assert [row["hypothesis_id"] for row in rows] == list(HYPOTHESIS_IDS)
    assert rows[3]["status"] == "SUPPORTED"
    assert rows[8]["status"] == "PARTIALLY_SUPPORTED"


def test_unknown_status_is_rejected():
    rows = build_hypothesis_rows({})
    rows[0]["status"] = "PROBABLY"
    with pytest.raises(Day6HypothesisError, match="status"):
        validate_hypothesis_rows(rows)
