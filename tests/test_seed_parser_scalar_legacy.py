from eval.stage2_failure_day13_seeds import extract_seed_values_with_provenance


def test_seed_parser_accepts_legacy_scalar_integer() -> None:
    records = extract_seed_values_with_provenance(123, "$.geometry_seed")
    assert records == [{
        "seed_value": 123,
        "source_file": "<memory>",
        "json_path": "$.geometry_seed",
        "container_type": "scalar",
        "seed_type": "geometry",
        "declared_seed_type": "geometry",
    }]
