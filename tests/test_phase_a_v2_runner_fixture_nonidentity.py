import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/fixture_tables/raw_trial_inventory.csv"


def test_nonidentity_fixture_passes_both_backends() -> None:
    with TABLE.open(newline="", encoding="utf-8") as stream:
        rows = [row for row in csv.DictReader(stream) if row["condition"] == "FIXTURE_NONIDENTITY_REFERENCE"]
    assert len(rows) == 2
    assert all(row["solver_failure"] == "False" and row["failure_classification"] == "NONE" for row in rows)

