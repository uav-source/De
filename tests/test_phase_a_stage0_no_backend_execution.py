from pathlib import Path

from backend_phase_a_v1_2_test_support import ROOT


def test_stage0_entrypoints_do_not_call_registration_functions():
    text = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in ("scripts/169_build_backend_phase_a_stage0.py", "scripts/170_verify_backend_phase_a_stage0.py"))
    assert "run_open3d" not in text
    assert "run_pcl" not in text
    assert "run_native" not in text
    assert "execute_formal_phase_a" not in text
