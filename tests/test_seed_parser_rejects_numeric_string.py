import pytest

from eval.stage2_failure_day13_seeds import extract_seed_values_with_provenance


def test_seed_parser_rejects_numeric_string() -> None:
    with pytest.raises(ValueError, match=r"string is not a seed at \$\.geometry_seed"):
        extract_seed_values_with_provenance("123", "$.geometry_seed")
