from __future__ import annotations

import importlib.util
import json
import os
import signal
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_supervisor():
    path = ROOT / "scripts/57_run_day5_startup_sync_v4_supervisor.py"
    spec = importlib.util.spec_from_file_location("day5_v4_supervisor", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fixed_order_is_quick_then_outdoor_and_audit_only() -> None:
    module = load_supervisor()
    plan = module.fixed_run_order()
    assert [row["sequence_id"] for row in plan] == [
        "avia_quick_shack",
        "avia_quick_shack",
        "avia_quick_shack",
        "avia_outdoor_run_100hz",
        "avia_outdoor_run_100hz",
        "avia_outdoor_run_100hz",
    ]
    assert [row["repeat_id"] for row in plan] == [1, 2, 3, 1, 2, 3]
    assert {row["runtime_mode"] for row in plan} == {"AUDIT_ONLY"}


def test_existing_run_root_is_rejected_except_stdio_reservation(tmp_path: Path) -> None:
    module = load_supervisor()
    run_root = tmp_path / "run"
    run_root.mkdir()
    (run_root / "old.json").write_text("{}")
    with pytest.raises(RuntimeError, match="consumed"):
        module.validate_reserved_run_root(run_root)
    (run_root / "old.json").unlink()
    (run_root / "supervisor.log").write_text("")
    module.validate_reserved_run_root(run_root)


def test_atomic_state_is_complete_json(tmp_path: Path) -> None:
    module = load_supervisor()
    path = tmp_path / "state.json"
    module.atomic_json(path, {"status": "CREATED", "run_id": module.RUN_ID})
    assert json.loads(path.read_text())["status"] == "CREATED"
    assert not list(tmp_path.glob("*.tmp"))


def test_exclusive_lock_blocks_second_instance(tmp_path: Path) -> None:
    module = load_supervisor()
    first = module.Supervisor(
        run_root=tmp_path / "one",
        endpoint_contract=tmp_path / "endpoint",
        run_lock=tmp_path / "run-lock",
        lock_path=tmp_path / "exclusive.lock",
    )
    second = module.Supervisor(
        run_root=tmp_path / "two",
        endpoint_contract=tmp_path / "endpoint",
        run_lock=tmp_path / "run-lock",
        lock_path=tmp_path / "exclusive.lock",
    )
    first.acquire_lock()
    with pytest.raises(RuntimeError, match="exclusive lock"):
        second.acquire_lock()


def test_sigterm_marks_interruption_and_terminates_owned_child(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = load_supervisor()
    supervisor = module.Supervisor(
        run_root=tmp_path,
        endpoint_contract=tmp_path / "endpoint",
        run_lock=tmp_path / "run-lock",
        lock_path=tmp_path / "lock",
    )

    class Child:
        pid = 123

        @staticmethod
        def poll():
            return None

    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "killpg", lambda pid, sig: calls.append((pid, sig)))
    supervisor.current_child = Child()
    supervisor.signal_handler(signal.SIGTERM, None)
    assert supervisor.interrupted
    assert supervisor.runner_interruption_count == 1
    assert calls == [(123, signal.SIGTERM)]


def test_terminal_state_set_is_fail_closed() -> None:
    module = load_supervisor()
    assert "COMPLETED" in module.TERMINAL_STATES
    assert "INTERRUPTED" in module.TERMINAL_STATES
    assert "OUTDOOR_RUNNING" not in module.TERMINAL_STATES
    assert "CAPTURE_ONLY" not in json.dumps(module.fixed_run_order())
    assert "COMPACT_EXPORT" not in json.dumps(module.fixed_run_order())
