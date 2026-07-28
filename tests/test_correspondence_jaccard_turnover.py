import pytest

from zero_perturbation.correspondence_turnover import jaccard_turnover


def test_correspondence_jaccard_turnover_and_empty_reason():
    value, reason = jaccard_turnover({1, 2}, {2, 3})
    assert value == pytest.approx(2.0 / 3.0)
    assert reason == ""
    assert jaccard_turnover(set(), set()) == (None, "EMPTY_CORRESPONDENCE_UNION")
