import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def taxonomy():
    return json.loads(
        (
            ROOT
            / "manifests/harmful_bias/day7_map_mutation_outcome_taxonomy.json"
        ).read_text(encoding="utf-8")
    )


def test_taxonomy_has_all_twenty_unique_formal_outcomes():
    value = taxonomy()
    outcomes = value["outcomes"]
    assert value["formal_outcome_count"] == 20
    assert len(outcomes) == 20
    assert {row["id"] for row in outcomes} == set(range(1, 21))
    assert len({row["name"] for row in outcomes}) == 20


def test_taxonomy_is_confirmed_and_fail_closed():
    value = taxonomy()
    assert value["source_resolution_status"] == "CONFIRMED"
    assert value["unclassified_formal_path_count"] == 0
    assert value["day7_outcome_taxonomy_pass"] is True
    assert value["sentinel"] == {
        "id": 255,
        "name": "UNCLASSIFIED_FORMAL_PATH",
        "runtime_allowed": False,
    }
