from pathlib import Path

import pytest

from fastlio2_adapter.day6_fallback_functional_diagnostics import (
    Day6FallbackError,
    EXPECTED_ENVIRONMENT,
    validate_environment_lock,
)


ROOT = Path(__file__).resolve().parents[1]


def test_locked_detector_environment(monkeypatch):
    for name, value in EXPECTED_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    identity = validate_environment_lock()
    assert identity["python_version"] == "3.8.10"
    assert identity["numpy_version"] == "1.24.4"
    assert identity["scipy_version"] == "1.10.1"


def test_detector_environment_version_or_variable_change_fails(monkeypatch):
    for name, value in EXPECTED_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("OMP_NUM_THREADS", "2")
    with pytest.raises(Day6FallbackError, match="environment variable"):
        validate_environment_lock()


def test_latency_is_not_written_into_canonical_output_source():
    source = (
        ROOT / "scripts/76_process_day6_fallback_detector.py"
    ).read_text(encoding="utf-8")
    assert "adapter_total_call_latency_ns" in source
    canonical = (
        ROOT / "src/fastlio2_adapter/canonical_detector_output.py"
    ).read_text(encoding="utf-8")
    assert "adapter_total_call_latency_ns" not in canonical
