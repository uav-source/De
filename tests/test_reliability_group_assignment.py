from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_structural_pilot_reliability_groups_are_134_and_5():
    rows = []
    import csv

    with (ROOT / "artifacts/current/measurement_real_validation_pilot/tables/weak_direction_accuracy.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))
    reliable = [row for row in rows if row["direction_reliable"] == "True"]
    unreliable = [row for row in rows if row["direction_reliable"] == "False"]
    assert (len(reliable), len(unreliable)) == (134, 5)
    assert float(__import__("numpy").median([float(row["angle_error_deg"]) for row in reliable])) == pytest.approx(30.8003, abs=1e-4)
    assert float(__import__("numpy").median([float(row["angle_error_deg"]) for row in unreliable])) == pytest.approx(28.9799, abs=1e-4)
