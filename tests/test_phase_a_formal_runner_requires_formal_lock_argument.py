import importlib.util

from phase_a_formal_lock_test_support import ROOT


def test_formal_runner_requires_only_the_strict_formal_lock_argument():
    script = ROOT / "scripts/168_run_backend_phase_a.py"
    spec = importlib.util.spec_from_file_location("formal_runner_v1_1", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    actions = {option: action for action in module.build_parser()._actions for option in action.option_strings}
    assert actions["--formal-execution-lock"].required is True
    assert "--execution-lock" not in actions
