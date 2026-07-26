import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("startup_runner", ROOT / "scripts/50_run_day5_startup_sync_matrix.py")
M = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(M)


def test_six_run_order_is_fixed_and_audit_only():
    plan = M.fixed_replay_plan()
    assert [(row["sequence_id"], row["repeat_id"]) for row in plan] == [
        ("avia_quick_shack", 1), ("avia_quick_shack", 2), ("avia_quick_shack", 3),
        ("avia_outdoor_run_100hz", 1), ("avia_outdoor_run_100hz", 2), ("avia_outdoor_run_100hz", 3),
    ]
    assert {row["mode"] for row in plan} == {"AUDIT_ONLY"}


def test_plan_rejects_development_holdout_future_or_extra_run():
    plan = M.fixed_replay_plan(); plan.append({"sequence_id": "Development", "repeat_id": 1, "mode": "AUDIT_ONLY"})
    with pytest.raises(ValueError):
        M.validate_replay_plan(plan)


def test_runner_command_rejects_unsupported_sequence():
    with pytest.raises(ValueError):
        M.build_handshake_command(
            root=ROOT,
            run_id=M.RUN_ID,
            sequence_id="Holdout",
            repeat_id=1,
            master_uri="http://127.0.0.1:19711",
            output=Path("handshake.json"),
        )


def test_shell_uses_paused_player_then_handshake_then_service_unpause():
    text = (ROOT / "scripts/50_run_day5_startup_sync_matrix.py").read_text()
    paused = text.index('"rosbag", "play", str(clip_path), "--pause"')
    handshake = text.index("handshake_command = build_handshake_command", paused)
    wait = text.index("rosbag.wait", paused)
    assert paused < handshake < wait
    assert "scripts/43_run_fastlio2_quick_equivalence.sh" not in text
    assert "date +%s%N" not in text
    assert "rosservice call" not in text
    assert "__name:=day5_bag_player" in text


def test_fresh_run_marker_forbids_reuse():
    text = (ROOT / "scripts/50_run_day5_startup_sync_matrix.py").read_text()
    assert "startup-sync V3 run-id has already been used" in text
    assert "RUN_ID_CONSUMED_NO_REUSE" in text


def test_prepared_source_locks_are_installed_without_modification(tmp_path):
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    source_lock = prepared / "fastlio2_source_lock_v3.json"
    source_lock.write_text("{}\n")
    run_lock = prepared / "day5_startup_sync_v3_run_lock.json"
    run_lock.write_text("{\"run_id\": \"fixture\"}\n")
    run_root = tmp_path / "run"
    run_root.mkdir()
    installed = M.install_prepared_locks(
        prepared_lock=run_lock,
        lock={"prepared_lock_files": ["source_locks/fastlio2_source_lock_v3.json"]},
        run_root=run_root,
    )
    assert installed.read_bytes() == run_lock.read_bytes()
    assert (run_root / "source_locks/fastlio2_source_lock_v3.json").read_bytes() == source_lock.read_bytes()
