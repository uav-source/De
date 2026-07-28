import csv

from eval.seed_provenance_audit import audit_seed_provenance


def test_seed_provenance_ignores_metric_values(tmp_path):
    candidate = 987654321
    with (tmp_path / "trial_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["trial_id", "correspondence_count", "error", "checksum"])
        writer.writerow([candidate, candidate, candidate, "aa{}bb".format(candidate)])
    audit = audit_seed_provenance(tmp_path, [candidate])
    assert audit["collision_count"] == 0

