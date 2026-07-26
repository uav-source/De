import importlib.util
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "startup_runner_shutdown",
    ROOT / "scripts/50_run_day5_startup_sync_matrix.py",
)
M = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(M)


class Process:
    pid = 123

    def __init__(self, timeout=False):
        self.timeout = timeout
        self.terminated = False
        self.killed = False

    def wait(self, timeout):
        if self.timeout and not self.terminated:
            raise subprocess.TimeoutExpired("roslaunch", timeout)
        return 0

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


def completed(*args, **kwargs):
    return subprocess.CompletedProcess(args[0], 0, "killed\n")


def test_rosnode_kill_normal_shutdown_has_no_forced_termination(tmp_path, monkeypatch):
    monkeypatch.setattr(M.subprocess, "run", completed)
    result = M.graceful_shutdown_roslaunch(
        Process(), environment={}, run_dir=tmp_path, timeout=0.01
    )
    assert result["shutdown_completed"] is True
    assert result["shutdown_request_method"] == "rosnode kill /laserMapping"
    assert result["forced_terminate_used"] is False
    assert result["forced_kill_used"] is False


def test_shutdown_timeout_is_failure_and_records_forced_terminate(tmp_path, monkeypatch):
    monkeypatch.setattr(M.subprocess, "run", completed)
    with pytest.raises(M.MatrixFailure) as caught:
        M.graceful_shutdown_roslaunch(
            Process(timeout=True), environment={}, run_dir=tmp_path, timeout=0.01
        )
    assert caught.value.classification == "RUNTIME_NODE_SHUTDOWN_INCOMPLETE"
