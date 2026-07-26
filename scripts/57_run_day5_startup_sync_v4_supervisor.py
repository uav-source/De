#!/usr/bin/env python3
"""Persistent fixed-order supervisor for the Day 5 startup-sync V4 matrix."""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "multihyp_day5_startup_sync_v4"
SEQUENCES = ("avia_quick_shack", "avia_outdoor_run_100hz")
REPEATS = (1, 2, 3)
RUN_ORDER = tuple(
    (sequence, repeat) for sequence in SEQUENCES for repeat in REPEATS
)
HEARTBEAT_INTERVAL_SEC = 5.0
TERMINAL_STATES = {
    "QUICK_FAILED",
    "COMPLETED",
    "FAILED",
    "INTERRUPTED",
}


def atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(str(path.parent), os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fixed_run_order() -> list[dict[str, Any]]:
    return [
        {
            "sequence_id": sequence,
            "repeat_id": repeat,
            "runtime_mode": "AUDIT_ONLY",
        }
        for sequence, repeat in RUN_ORDER
    ]


def validate_reserved_run_root(path: Path) -> None:
    if not path.exists():
        return
    entries = {child.name for child in path.iterdir()}
    if entries - {"supervisor.log"}:
        raise RuntimeError(f"run-root already consumed: {path}")
    log = path / "supervisor.log"
    if log.exists() and not log.is_file():
        raise RuntimeError("reserved supervisor.log is not a regular file")


class Supervisor:
    def __init__(
        self,
        *,
        run_root: Path,
        endpoint_contract: Path,
        run_lock: Path,
        lock_path: Path,
    ) -> None:
        self.run_root = run_root
        self.external_endpoint = endpoint_contract
        self.external_run_lock = run_lock
        self.lock_path = lock_path
        self.current_child: subprocess.Popen[Any] | None = None
        self.current_sequence: str | None = None
        self.current_repeat: int | None = None
        self.status = "CREATED"
        self.started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.last_heartbeat_ns = 0
        self.heartbeat_count = 0
        self.runner_interruption_count = 0
        self.interrupted = False
        self.failure_classification = "NONE"
        self.failure_message = ""
        self._lock_handle: Any | None = None

    def acquire_lock(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_handle = self.lock_path.open("a+")
        try:
            fcntl.flock(
                self._lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
            )
        except BlockingIOError as error:
            raise RuntimeError("another V4 supervisor owns the exclusive lock") from error
        self._lock_handle.seek(0)
        self._lock_handle.truncate()
        self._lock_handle.write(f"{os.getpid()}\n")
        self._lock_handle.flush()
        os.fsync(self._lock_handle.fileno())

    def install_inputs(self) -> tuple[Path, Path]:
        validate_reserved_run_root(self.run_root)
        self.run_root.mkdir(parents=True, exist_ok=True)
        external_lock = json.loads(
            self.external_run_lock.read_text(encoding="utf-8")
        )
        if external_lock.get("run_id") != RUN_ID:
            raise RuntimeError("run lock does not authorize the fixed V4 run-id")
        if external_lock.get("run_order") != fixed_run_order():
            raise RuntimeError("run lock replay order mismatch")
        endpoint_sha = file_sha256(self.external_endpoint)
        if endpoint_sha != external_lock.get("endpoint_contract_sha256"):
            raise RuntimeError("endpoint contract SHA mismatch")
        installed_endpoint = self.run_root / "replay_endpoint_contract_v1.json"
        installed_lock = self.run_root / "day5_startup_sync_v4_run_lock.json"
        shutil.copy2(self.external_endpoint, installed_endpoint)
        shutil.copy2(self.external_run_lock, installed_lock)
        for relative in (
            external_lock["degen_source_lock_path"],
            external_lock["fastlio2_source_lock_path"],
        ):
            source = self.external_run_lock.parent / Path(relative).name
            destination = self.run_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        atomic_json(
            self.run_root / "endpoint_contract_validation.json",
            {
                "REPLAY_ENDPOINT_CONTRACT_PASS": True,
                "endpoint_contract_sha256": endpoint_sha,
                "byte_identical_generation_pass": external_lock[
                    "endpoint_contract_determinism_pass"
                ],
            },
        )
        (self.run_root / "matrix_started.marker").write_text(
            "RUN_ID_CONSUMED_NO_REUSE\n", encoding="utf-8"
        )
        (self.run_root / "supervisor.pid").write_text(
            f"{os.getpid()}\n", encoding="utf-8"
        )
        return installed_endpoint, installed_lock

    def matrix_state(self) -> dict[str, Any]:
        return {
            "schema_version": "day5_startup_sync_v4_matrix_state_v1",
            "run_id": RUN_ID,
            "status": self.status,
            "supervisor_pid": os.getpid(),
            "parent_pid": os.getppid(),
            "current_sequence": self.current_sequence,
            "current_repeat": self.current_repeat,
            "current_child_pid": (
                self.current_child.pid if self.current_child is not None else None
            ),
            "run_order": fixed_run_order(),
            "runner_interruption_count": self.runner_interruption_count,
            "failure_classification": self.failure_classification,
            "failure_message": self.failure_message,
            "started_at_utc": self.started_at,
            "updated_at_utc": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            ),
        }

    def write_state(self, status: str) -> None:
        self.status = status
        atomic_json(self.run_root / "matrix_state.json", self.matrix_state())

    def heartbeat(self, *, force: bool = False) -> None:
        now = time.monotonic_ns()
        if (
            not force
            and self.last_heartbeat_ns
            and now - self.last_heartbeat_ns
            < int(HEARTBEAT_INTERVAL_SEC * 1e9)
        ):
            return
        self.last_heartbeat_ns = now
        self.heartbeat_count += 1
        row = {
            "supervisor_pid": os.getpid(),
            "parent_pid": os.getppid(),
            "run_id": RUN_ID,
            "current_phase": self.status,
            "current_sequence": self.current_sequence or "",
            "current_repeat": self.current_repeat or "",
            "current_child_pid": (
                self.current_child.pid if self.current_child is not None else ""
            ),
            "last_heartbeat_monotonic_ns": now,
            "started_at_utc": self.started_at,
            "updated_at_utc": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            ),
        }
        atomic_json(self.run_root / "supervisor_heartbeat.json", row)
        history = self.run_root / "supervisor_heartbeat_history.csv"
        exists = history.exists()
        with history.open("a", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(row))
            if not exists:
                writer.writeheader()
            writer.writerow(row)
            stream.flush()
            os.fsync(stream.fileno())

    def signal_handler(self, _signum: int, _frame: object) -> None:
        self.interrupted = True
        self.runner_interruption_count += 1
        if self.current_child is not None and self.current_child.poll() is None:
            try:
                os.killpg(self.current_child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    def run_child(
        self, sequence: str, repeat: int, endpoint: Path, run_lock: Path
    ) -> int:
        self.current_sequence = sequence
        self.current_repeat = repeat
        command = [
            sys.executable,
            str(ROOT / "scripts/56_run_single_startup_sync_v4.py"),
            "--run-id",
            RUN_ID,
            "--sequence-id",
            sequence,
            "--repeat-id",
            str(repeat),
            "--run-root",
            str(self.run_root),
            "--endpoint-contract",
            str(endpoint),
            "--run-lock",
            str(run_lock),
        ]
        log = self.run_root / f"single_{sequence}_R{repeat}.log"
        with log.open("w", encoding="utf-8") as stream:
            self.current_child = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                text=True,
            )
            self.write_state(self.status)
            while self.current_child.poll() is None:
                if self.interrupted:
                    break
                self.heartbeat()
                time.sleep(1.0)
            code = self.current_child.wait()
        self.current_child = None
        self.heartbeat(force=True)
        return code

    def compare_quick(self, endpoint: Path, run_lock: Path) -> bool:
        self.write_state("QUICK_COMPARING")
        self.heartbeat(force=True)
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/58_finalize_day5_startup_sync_v4.py"),
                "--run-root",
                str(self.run_root),
                "--endpoint-contract",
                str(endpoint),
                "--run-lock",
                str(run_lock),
                "--quick-gate",
            ],
            cwd=ROOT,
            stdout=(self.run_root / "quick_comparison.log").open(
                "w", encoding="utf-8"
            ),
            stderr=subprocess.STDOUT,
        )
        return completed.returncode == 0

    def final_compare(self, endpoint: Path, run_lock: Path) -> bool:
        self.write_state("OUTDOOR_COMPARING")
        self.heartbeat(force=True)
        with (self.run_root / "finalize_v4.log").open(
            "w", encoding="utf-8"
        ) as stream:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/58_finalize_day5_startup_sync_v4.py"),
                    "--run-root",
                    str(self.run_root),
                    "--endpoint-contract",
                    str(endpoint),
                    "--run-lock",
                    str(run_lock),
                ],
                cwd=ROOT,
                stdout=stream,
                stderr=subprocess.STDOUT,
            )
        return completed.returncode == 0

    def run(self) -> int:
        self.acquire_lock()
        endpoint, run_lock = self.install_inputs()
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
        self.write_state("CREATED")
        self.heartbeat(force=True)
        for sequence in SEQUENCES:
            self.write_state(
                "QUICK_RUNNING"
                if sequence == "avia_quick_shack"
                else "OUTDOOR_RUNNING"
            )
            for repeat in REPEATS:
                code = self.run_child(sequence, repeat, endpoint, run_lock)
                if self.interrupted:
                    self.failure_classification = "RUNNER_SESSION_INTERRUPTED"
                    self.failure_message = "supervisor received termination signal"
                    self.write_state("INTERRUPTED")
                    self.heartbeat(force=True)
                    return 130
                if code != 0:
                    failure_path = (
                        self.run_root
                        / "runs/baseline"
                        / sequence
                        / f"AUDIT_ONLY_R{repeat}"
                        / "single_run_failure.json"
                    )
                    failure = (
                        json.loads(failure_path.read_text(encoding="utf-8"))
                        if failure_path.is_file()
                        else {}
                    )
                    self.failure_classification = failure.get(
                        "failure_classification", "RUNTIME_PRODUCT_MISSING"
                    )
                    self.failure_message = failure.get(
                        "message",
                        f"single runner failed: {sequence} R{repeat} exit={code}",
                    )
                    self.write_state("FAILED")
                    self.heartbeat(force=True)
                    return 30
            if sequence == "avia_quick_shack" and not self.compare_quick(
                endpoint, run_lock
            ):
                self.failure_classification = (
                    "INPUT_BOUNDARY_NONDETERMINISM_AFTER_DRAIN"
                )
                self.failure_message = "Quick strict repeatability gate failed"
                self.write_state("QUICK_FAILED")
                self.heartbeat(force=True)
                return 20
        passed = self.final_compare(endpoint, run_lock)
        if not passed:
            summary_path = self.run_root / "day5_startup_sync_v4_summary.json"
            if summary_path.is_file():
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                self.failure_classification = summary.get(
                    "FAILURE_CLASSIFICATION", "RUNTIME_PRODUCT_MISSING"
                )
            else:
                self.failure_classification = "RUNTIME_PRODUCT_MISSING"
            self.failure_message = "final strict repeatability gate failed"
            self.write_state("FAILED")
            self.heartbeat(force=True)
            return 20
        self.write_state("COMPLETED")
        self.heartbeat(force=True)
        shutil.copy2(
            self.run_root / "matrix_state.json",
            self.run_root / "supervisor_final_state.json",
        )
        heartbeat_times: list[int] = []
        with (self.run_root / "supervisor_heartbeat_history.csv").open(
            encoding="utf-8", newline=""
        ) as stream:
            heartbeat_times = [
                int(row["last_heartbeat_monotonic_ns"])
                for row in csv.DictReader(stream)
            ]
        max_gap = max(
            (
                (right - left) / 1e9
                for left, right in zip(heartbeat_times, heartbeat_times[1:])
            ),
            default=0.0,
        )
        with (self.run_root / "supervisor_heartbeat_summary.csv").open(
            "w", encoding="utf-8", newline=""
        ) as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=(
                    "supervisor_pid",
                    "heartbeat_count",
                    "max_heartbeat_gap_sec",
                    "runner_interruption_count",
                    "terminal_state",
                ),
            )
            writer.writeheader()
            writer.writerow(
                {
                    "supervisor_pid": os.getpid(),
                    "heartbeat_count": len(heartbeat_times),
                    "max_heartbeat_gap_sec": max_gap,
                    "runner_interruption_count": self.runner_interruption_count,
                    "terminal_state": "COMPLETED",
                }
            )
        with (self.run_root / "finalize_v4_terminal.log").open(
            "w", encoding="utf-8"
        ) as stream:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/58_finalize_day5_startup_sync_v4.py"),
                    "--run-root",
                    str(self.run_root),
                    "--endpoint-contract",
                    str(endpoint),
                    "--run-lock",
                    str(run_lock),
                ],
                cwd=ROOT,
                stdout=stream,
                stderr=subprocess.STDOUT,
            )
        return completed.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--endpoint-contract", required=True, type=Path)
    parser.add_argument("--run-lock", required=True, type=Path)
    parser.add_argument("--lock-path", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.run_id != RUN_ID:
        raise SystemExit("ERROR: only multihyp_day5_startup_sync_v4 is allowed")
    run_root = args.run_root.expanduser().resolve()
    lock_path = (
        args.lock_path.expanduser().resolve()
        if args.lock_path
        else run_root.parent / ".day5_startup_sync_v4_supervisor.lock"
    )
    supervisor = Supervisor(
        run_root=run_root,
        endpoint_contract=args.endpoint_contract.expanduser().resolve(),
        run_lock=args.run_lock.expanduser().resolve(),
        lock_path=lock_path,
    )
    try:
        return supervisor.run()
    except Exception as error:
        if run_root.exists():
            supervisor.failure_classification = "RUNNER_SESSION_INTERRUPTED"
            supervisor.failure_message = str(error)
            supervisor.write_state("FAILED")
            supervisor.heartbeat(force=True)
        print(f"ERROR: {error}", file=sys.stderr)
        return 30


if __name__ == "__main__":
    raise SystemExit(main())
