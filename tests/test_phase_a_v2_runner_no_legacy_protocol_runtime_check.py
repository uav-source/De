from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v2_engine_does_not_call_legacy_protocol_validator() -> None:
    source = (ROOT / "src/zero_perturbation/backend_phase_a_v2.py").read_text()
    assert "validate_protocol_lock(" not in source
    assert "--protocol-lock" not in (ROOT / "scripts/179_run_backend_phase_a_v2.py").read_text()

