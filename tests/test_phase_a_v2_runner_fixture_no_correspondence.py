import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/fixture_tables/raw_trial_inventory.csv"


def test_no_correspondence_fixture_has_expected_failures() -> None:
    with TABLE.open(newline="", encoding="utf-8") as stream:
        rows = [row for row in csv.DictReader(stream) if row["condition"] == "FIXTURE_NO_CORRESPONDENCE"]
    assert len(rows) == 2
    assert all(row["solver_failure"] == "True" and row["failure_classification"] == "NO_CORRESPONDENCES" for row in rows)

