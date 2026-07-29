from eval.stage2_failure_day13_seeds import extract_seed_values_with_provenance


def test_seed_parser_accepts_v2_objects_and_values_container() -> None:
    object_records = extract_seed_values_with_provenance(
        [
            {"index": 0, "label": "geometry_0", "value": 123},
            {"index": 1, "label": "geometry_1", "value": 456},
        ],
        "$.geometry_seeds",
    )
    values_records = extract_seed_values_with_provenance(
        {"values": [789, 987]},
        "$.process_seeds",
    )
    assert [row["seed_value"] for row in object_records] == [123, 456]
    assert [row["json_path"] for row in object_records] == [
        "$.geometry_seeds[0].value",
        "$.geometry_seeds[1].value",
    ]
    assert [row["seed_value"] for row in values_records] == [789, 987]
    assert [row["json_path"] for row in values_records] == [
        "$.process_seeds.values[0]",
        "$.process_seeds.values[1]",
    ]
