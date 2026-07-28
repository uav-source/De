import csv
import json

from eval.seed_provenance_audit import audit_seed_provenance


def test_seed_provenance_context_detection(tmp_path):
    candidate = 987654321
    (tmp_path / "run_manifest.json").write_text(
        json.dumps({"run": {"bootstrap_seed": candidate}}), encoding="utf-8"
    )
    with (tmp_path / "trials.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["trial_id", "geometry_seed"])
        writer.writerow([1, candidate])
    audit = audit_seed_provenance(tmp_path, [candidate])
    assert audit["collision_count"] == 2
    assert {row["context"] for row in audit["collisions"]} == {
        "structured_seed_field",
        "csv_seed_column",
    }

