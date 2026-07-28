from eval.seed_provenance_audit import audit_seed_provenance


def test_seed_provenance_detects_rng_initialization(tmp_path):
    candidate = 987654321
    (tmp_path / "runner.py").write_text(
        "import numpy as np\nrng = np.random.default_rng({})\n".format(candidate),
        encoding="utf-8",
    )
    audit = audit_seed_provenance(tmp_path, [candidate])
    assert audit["collision_count"] == 1
    assert audit["collisions"][0]["context"] == "python_rng_initialization"

