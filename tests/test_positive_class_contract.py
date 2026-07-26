import pytest

from eval.metric_semantics import (
    NEGATIVE_CLASS,
    POSITIVE_CLASS,
    POSITIVE_CLASS_VALUE,
    positive_class_value,
)


def test_structural_candidate_is_the_only_frozen_positive_class():
    assert POSITIVE_CLASS == "structural_degeneracy_candidate"
    assert POSITIVE_CLASS_VALUE == 1
    assert positive_class_value(POSITIVE_CLASS) == 1
    assert positive_class_value(NEGATIVE_CLASS) == 0
    with pytest.raises(ValueError, match="outside"):
        positive_class_value("outside")
