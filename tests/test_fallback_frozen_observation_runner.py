import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def runner():
    path = ROOT / "scripts/66_run_fallback_frozen_observation.py"
    spec = importlib.util.spec_from_file_location("frozen_runner", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_identity_is_one_fixed_quick_run():
    module = runner()
    assert module.RUN_ID == "multihyp_fallback_frozen_observation_v1"
    assert module.SEQUENCE_ID == "avia_quick_shack"
    assert module.REPEAT_ID == 1


def test_runner_uses_compact_minimal_export():
    module = runner()
    assert module.FAST_RUNTIME_MODE == "COMPACT_EXPORT"
    assert module.PAYLOAD_PROFILE == "DETECTOR_MINIMAL_V1"
    assert module.TAP_BUFFER_CAPACITY == 1024


def test_runner_captures_in_call_status_before_shutdown():
    source = (
        ROOT / "scripts/66_run_fallback_frozen_observation.py"
    ).read_text()
    service = source.index("module.bounded_trigger_call(")
    shutdown = source.index("return original_shutdown(", service)
    assert service < shutdown


def test_runner_contains_no_detector_or_odi_call():
    source = (
        ROOT / "scripts/66_run_fallback_frozen_observation.py"
    ).read_text().lower()
    assert "degen_detector" not in source
    assert "compute_odi(" not in source
