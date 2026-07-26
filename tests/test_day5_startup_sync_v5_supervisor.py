from __future__ import annotations

import importlib.util
import json
import os
import signal
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_supervisor():
    path = ROOT / "scripts/61_run_day5_startup_sync_v5_supervisor.py"
    spec = importlib.util.spec_from_file_location(
        "day5_v5_supervisor", path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def supervisor(module, tmp_path: Path):
    return module.Supervisor(
        run_root=tmp_path / "run",
        endpoint_contract=tmp_path / "endpoint",
        run_lock=tmp_path / "run-lock",
        lock_path=tmp_path / "exclusive.lock",
    )


def test_fixed_order_is_six_audit_only_replays() -> None:
    module = load_supervisor()
    plan = module.fixed_run_order()
    assert [
        (row["sequence_id"], row["repeat_id"]) for row in plan
    ] == [
        ("avia_quick_shack", 1),
        ("avia_quick_shack", 2),
        ("avia_quick_shack", 3),
        ("avia_outdoor_run_100hz", 1),
        ("avia_outdoor_run_100hz", 2),
        ("avia_outdoor_run_100hz", 3),
    ]
    assert {row["runtime_mode"] for row in plan} == {"AUDIT_ONLY"}


def test_wall_timeouts_and_heartbeat_are_frozen() -> None:
    module = load_supervisor()
    assert module.SINGLE_RUN_WALL_TIMEOUTS == {
        "avia_quick_shack": 450.0,
        "avia_outdoor_run_100hz": 510.0,
    }
    assert module.HEARTBEAT_INTERVAL_SEC == 5.0
    assert module.RUNNER_HEARTBEAT_STALE_SEC == 20.0


def test_existing_run_root_is_fail_closed(tmp_path: Path) -> None:
    module = load_supervisor()
    run_root = tmp_path / "run"
    run_root.mkdir()
    (run_root / "old.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="consumed"):
        module.validate_reserved_run_root(run_root)


def test_exclusive_lock_blocks_second_supervisor(tmp_path: Path) -> None:
    module = load_supervisor()
    first = supervisor(module, tmp_path)
    second = module.Supervisor(
        run_root=tmp_path / "other",
        endpoint_contract=tmp_path / "endpoint",
        run_lock=tmp_path / "run-lock",
        lock_path=tmp_path / "exclusive.lock",
    )
    first.acquire_lock()
    with pytest.raises(RuntimeError, match="exclusive lock"):
        second.acquire_lock()


def test_signal_only_terminates_owned_child(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = load_supervisor()
    instance = supervisor(module, tmp_path)

    class Child:
        pid = 123

        @staticmethod
        def poll():
            return None

    calls = []
    monkeypatch.setattr(
        os, "killpg", lambda pid, sig: calls.append((pid, sig))
    )
    instance.current_child = Child()
    instance.signal_handler(signal.SIGTERM, None)
    assert instance.interrupted
    assert instance.runner_interruption_count == 1
    assert calls == [(123, signal.SIGTERM)]


def test_terminal_evidence_is_small_and_explicit(tmp_path: Path) -> None:
    module = load_supervisor()
    instance = supervisor(module, tmp_path)
    instance.run_root.mkdir()
    instance.write_state("FAILED")
    instance.heartbeat(force=True)
    instance.failure_classification = "TAIL_CLOCK_START_FAILURE"
    instance.write_state("FAILED")
    instance.write_terminal_evidence()
    final = json.loads(
        (instance.run_root / "supervisor_final_state.json").read_text()
    )
    assert final["status"] == "FAILED"
    assert final["failure_classification"] == "TAIL_CLOCK_START_FAILURE"
    assert (instance.run_root / "supervisor_summary.csv").is_file()

