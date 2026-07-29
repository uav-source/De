from eval.stage2_failure_day13_seeds import extract_typed_seed_provenance


def test_seed_parser_preserves_source_and_full_json_paths() -> None:
    records = extract_typed_seed_provenance(
        {"nested": {"geometry_seeds": {"values": [123, 456]}}},
        source_file="fixture.json",
    )
    assert [(row["source_file"], row["json_path"]) for row in records] == [
        ("fixture.json", "$.nested.geometry_seeds.values[0]"),
        ("fixture.json", "$.nested.geometry_seeds.values[1]"),
    ]
