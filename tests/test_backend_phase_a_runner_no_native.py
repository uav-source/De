import importlib.util

from backend_phase_a_v1_1_test_support import ROOT


def test_runner_cli_has_no_native_or_backend_subset_entry():
    path = ROOT / "scripts/168_run_backend_phase_a.py"
    spec = importlib.util.spec_from_file_location("phase_a_v1_1_runner_cli", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    options = {option for action in module.build_parser()._actions for option in action.option_strings}
    assert "--native" not in options
    assert "--backend-subset" not in options
    assert "--exclude-scene" not in options

