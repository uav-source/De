import csv

from backend_phase_a_test_support import ARTIFACT


def test_plan_csvs_have_exact_rows_ids_and_no_point_cloud_fields():
    with (ARTIFACT / "planned_snapshots.csv").open(newline="", encoding="utf-8") as stream:
        snapshots = list(csv.DictReader(stream))
    with (ARTIFACT / "planned_trials.csv").open(newline="", encoding="utf-8") as stream:
        trials = list(csv.DictReader(stream))
    assert len(snapshots) == 210
    assert len(trials) == 420
    assert len({row["snapshot_id"] for row in snapshots}) == 210
    assert len({row["planned_trial_id"] for row in trials}) == 420
    assert snapshots[0]["snapshot_id"] == "phase-a-v1/GEOMETRY_RICH_ROOM/0/0/0"
    assert not {"source_points", "target_points", "pcd_path"} & set(snapshots[0])
