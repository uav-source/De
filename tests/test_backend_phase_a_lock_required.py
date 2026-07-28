import importlib.util

import pytest

from backend_phase_a_test_support import ROOT


def test_phase_a_execution_parser_requires_protocol_lock_and_has_no_override_flags():
    path = ROOT / "scripts/168_run_backend_phase_a.py"
    spec = importlib.util.spec_from_file_location("phase_a_runner_contract", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    with pytest.raises(SystemExit):
        module.build_parser().parse_args([])
    source = path.read_text(encoding="utf-8")
    assert '"--protocol-lock"' in source
    assert "--ignore-lock" not in source
    assert "--override-parameters" not in source
    assert "--change-thresholds" not in source
