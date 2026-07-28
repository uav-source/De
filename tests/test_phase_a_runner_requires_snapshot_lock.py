import importlib.util

import pytest

from backend_phase_a_v1_2_test_support import ROOT


def test_stage1_runner_parser_requires_snapshot_lock():
    path = ROOT / "scripts/168_run_backend_phase_a.py"
    spec = importlib.util.spec_from_file_location("stage1_runner_requires_lock", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    with pytest.raises(SystemExit):
        module.build_parser().parse_args(["--protocol-lock", "x", "--run-id", "x", "--output-dir", "x", "--workers", "1"])
