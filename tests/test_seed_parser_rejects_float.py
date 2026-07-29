import pytest

from eval.stage2_failure_day13_seeds import extract_seed_values_with_provenance


def test_seed_parser_rejects_integral_float() -> None:
    with pytest.raises(ValueError, match=r"float is not a seed at \$\.geometry_seed"):
        extract_seed_values_with_provenance(123.0, "$.geometry_seed")
