from eval.stage2_failure_day13_seeds import extract_seed_values_with_provenance


def test_seed_parser_accepts_legacy_integer_list() -> None:
    records = extract_seed_values_with_provenance([123, 456], "$.sensor_seeds")
    assert [row["seed_value"] for row in records] == [123, 456]
    assert [row["json_path"] for row in records] == [
        "$.sensor_seeds[0]",
        "$.sensor_seeds[1]",
    ]
    assert {row["container_type"] for row in records} == {"list"}
