from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_runner():
    path = ROOT / "scripts/64_run_fallback_in_call_immutability.py"
    spec = importlib.util.spec_from_file_location("fallback_in_call_runner", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_identity_is_single_fixed_quick_run() -> None:
    module = load_runner()
    assert module.RUN_ID == "multihyp_fallback_in_call_v1"
    assert module.SEQUENCE_ID == "avia_quick_shack"
    assert module.REPEAT_ID == 1
    assert module.ENGINEERING_MODE == "FALLBACK_IN_CALL_AUDIT"


def test_runner_enables_tap_without_export_or_detector() -> None:
    module = load_runner()
    source = (
        ROOT / "scripts/64_run_fallback_in_call_immutability.py"
    ).read_text(encoding="utf-8")
    assert module.FAST_RUNTIME_MODE == "CAPTURE_ONLY"
    assert module.TAP_BUFFER_CAPACITY == 1024
    assert "COMPACT_EXPORT" not in source
    assert "degen_detector" not in source
    assert module.IN_CALL_STATUS_SERVICE in source


def test_status_is_captured_before_shutdown() -> None:
    source = (
        ROOT / "scripts/64_run_fallback_in_call_immutability.py"
    ).read_text(encoding="utf-8")
    service = source.index("module.bounded_trigger_call(")
    shutdown = source.index("return original_shutdown(", service)
    assert service < shutdown
