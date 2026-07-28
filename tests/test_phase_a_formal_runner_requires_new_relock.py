import importlib.util

import pytest

from phase_a_execution_chain_test_support import ROOT
from zero_perturbation.backend_phase_a_stage1 import validate_stage1_execution_lock


def test_formal_runner_cli_requires_new_execution_lock_and_rejects_missing_lock(tmp_path):
    script = ROOT / "scripts/168_run_backend_phase_a.py"
    spec = importlib.util.spec_from_file_location("formal_runner_relock", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    options = {option for action in module.build_parser()._actions for option in action.option_strings}
    assert "--formal-execution-lock" in options
    assert "--execution-lock" not in options
    with pytest.raises(FileNotFoundError):
        validate_stage1_execution_lock(tmp_path / "missing.json", root=ROOT, protocol_lock=tmp_path / "protocol.json", snapshot_lock=tmp_path / "snapshot.json")
