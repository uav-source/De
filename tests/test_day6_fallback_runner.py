import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_runner():
    path = ROOT / "scripts/75_run_day6_fallback_real_replay.py"
    spec = importlib.util.spec_from_file_location("day6_runner_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_runner_reuses_frozen_mixed_clock_rule():
    module = load_runner()
    raw = {
        "tail_clock_step_ns": 1_000_000,
        "last_bag_clock_ns": 10_000_000,
        "tail_first_clock_ns": 11_000_000,
        "tail_publish_count": 5,
        "tail_final_clock_ns": 15_000_000,
        "clock_publisher_overlap_count": 0,
        "clock_backward_count": 0,
        "clock_duplicate_count": 23,
        "handoff_pass": False,
    }
    result = module.adjudicate_tail(
        raw,
        raw_runner_exit_code=30,
        raw_failure_classification="NONE",
    )
    assert result["raw_runner_exit_code"] == 30
    assert result["raw_tail_handoff_pass"] is False
    assert result["adjudicated_tail_handoff_pass"] is True
    assert result["adjudicated_tail_duplicate_count"] == 0


def test_nonfrozen_tail_failure_does_not_pass():
    module = load_runner()
    raw = {
        "tail_clock_step_ns": 1_000_000,
        "last_bag_clock_ns": 10_000_000,
        "tail_first_clock_ns": 11_000_000,
        "tail_publish_count": 5,
        "tail_final_clock_ns": 99,
        "clock_publisher_overlap_count": 0,
        "clock_backward_count": 0,
        "clock_duplicate_count": 23,
        "handoff_pass": False,
    }
    result = module.adjudicate_tail(
        raw,
        raw_runner_exit_code=30,
        raw_failure_classification="RUNTIME_PRODUCT_MISSING",
    )
    assert result["adjudicated_tail_handoff_pass"] is False
