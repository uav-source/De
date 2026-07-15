from eval.stage2_failure_deterministic_case import build_candidate_pool, select_case
from eval.stage2_failure_day11a_schema import validate_candidate_pool_rows


def test_cartesian_candidate_pool_has_frozen_count_order_and_no_duplicates():
    rows = build_candidate_pool(
        "geometry",
        ["L3", "L4"],
        [10, 20],
        [1, 2],
        [100, 101],
    )
    assert len(rows) == 16
    keys = [
        (r["level"], r["geometry_seed"], r["sensor_seed"], r["process_seed"])
        for r in rows
    ]
    assert keys == sorted(keys)
    assert len(keys) == len(set(keys))
    assert rows[0]["canonical_candidate_string"] == (
        "level=L3|geometry_seed=10|sensor_seed=1|process_seed=100"
    )


def test_candidate_schema_requires_exactly_one_selected_row_per_sweep():
    geometry = build_candidate_pool("geometry", ["L3"], [10], [1], [100, 101])
    observation = build_candidate_pool(
        "observation", ["O3"], [10], [1], [100, 101]
    )
    _, _, geometry = select_case(geometry, "geometry-label")
    _, _, observation = select_case(observation, "observation-label")
    assert validate_candidate_pool_rows(geometry + observation, 2, 2) == {
        "candidate_duplicate_count": 0,
        "geometry_selected_row_count": 1,
        "observation_selected_row_count": 1,
    }


def test_candidate_schema_rejects_zero_or_multiple_selected_rows():
    geometry = build_candidate_pool("geometry", ["L3"], [10], [1], [100, 101])
    observation = build_candidate_pool("observation", ["O3"], [10], [1], [100])
    geometry[0]["selected"] = True
    observation[0]["selected"] = True
    validate_candidate_pool_rows(geometry + observation, 2, 1)

    geometry[0]["selected"] = False
    try:
        validate_candidate_pool_rows(geometry + observation, 2, 1)
    except ValueError as exc:
        assert "exactly one" in str(exc)
    else:
        raise AssertionError("zero selected Geometry rows must fail")

    geometry[0]["selected"] = True
    geometry[1]["selected"] = True
    try:
        validate_candidate_pool_rows(geometry + observation, 2, 1)
    except ValueError as exc:
        assert "exactly one" in str(exc)
    else:
        raise AssertionError("multiple selected Geometry rows must fail")


def test_candidate_pool_rejects_duplicate_seed_inputs():
    try:
        build_candidate_pool("geometry", ["L3"], [10, 10], [1], [100])
    except ValueError as exc:
        assert "duplicates" in str(exc)
    else:
        raise AssertionError("duplicate source seeds must fail")
