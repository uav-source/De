import pytest

from eval.stage2_failure_day13_seeds import extract_seed_values_with_provenance


def test_seed_parser_rejects_unknown_structured_leaf_with_path() -> None:
    with pytest.raises(
        ValueError,
        match=r"unrecognized seed container leaf at \$\.geometry_seeds\.unexpected",
    ):
        extract_seed_values_with_provenance(
            {"value": 123, "unexpected": 456},
            "$.geometry_seeds",
        )
