import json

from eval.seed_provenance_audit import audit_seed_provenance


def test_seed_provenance_detects_manifest_seed(tmp_path):
    candidate = 987654321
    (tmp_path / "protocol_lock.json").write_text(
        json.dumps({"reserved": {"measurement_seed": candidate}}), encoding="utf-8"
    )
    audit = audit_seed_provenance(tmp_path, [candidate])
    assert audit["collision_count"] == 1
    assert audit["collisions"][0]["field"] == "$.reserved.measurement_seed"

