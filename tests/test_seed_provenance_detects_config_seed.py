from eval.seed_provenance_audit import audit_seed_provenance


def test_seed_provenance_detects_config_seed(tmp_path):
    candidate = 987654321
    (tmp_path / "pilot.yaml").write_text(
        "geometry_seeds:\n  - {}\n".format(candidate), encoding="utf-8"
    )
    audit = audit_seed_provenance(tmp_path, [candidate])
    assert audit["collision_count"] == 1
    assert audit["collisions"][0]["field"] == "$.geometry_seeds[0]"

