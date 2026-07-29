from eval.stage2_failure_day13_seeds import extract_typed_seed_provenance


def test_seed_parser_does_not_expand_into_non_seed_numbers() -> None:
    records = extract_typed_seed_provenance({
        "translation_q95": 0.01,
        "rotation_threshold": 0.02,
        "geometry_seed_count": 3,
        "geometry_seed_index": 2,
        "trial_id": 123,
        "timestamp": 1850310744,
        "sha256": "1" * 64,
    })
    assert records == []
