from zero_perturbation.backend_phase_a_stage0_artifact import (
    REQUIRED_FILES,
    verify_sha256_manifest,
)


def test_stage0_artifact_contract_and_sha_verifier(tmp_path):
    assert len(REQUIRED_FILES) == 19
    payload = tmp_path / "evidence.txt"
    payload.write_text("locked\n", encoding="utf-8")
    import hashlib

    digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    (tmp_path / "SHA256SUMS").write_text(
        f"{digest}  evidence.txt\n", encoding="utf-8"
    )
    result = verify_sha256_manifest(tmp_path)
    assert result["pass"] is True
    assert result["entry_count"] == 1
