import pytest

from eval.stage2_failure_day13_seeds import extract_seed_values_with_provenance


def test_seed_parser_rejects_boolean_as_integer() -> None:
    with pytest.raises(ValueError, match=r"boolean is not a seed at \$\.geometry_seed"):
        extract_seed_values_with_provenance(True, "$.geometry_seed")
