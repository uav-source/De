"""Machine-verifiable pytest provenance for Stage 1c Engineering Gate."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import pytest

from .analysis_lock import compute_source_tree_hash, git_commit, git_status_clean, stage1c_source_paths


def _run_pytest_command(command: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess:
    """Narrow subprocess seam used only for the nested pytest invocation."""

    return subprocess.run(command, **kwargs)


def run_verified_pytest(root: Path, output_path: Path) -> Dict[str, Any]:
    root = Path(root).resolve()
    output = Path(output_path).resolve()
    clean_before = git_status_clean(root)
    commit = git_commit(root)
    source_hash = compute_source_tree_hash(stage1c_source_paths(root))
    command = [sys.executable, "-m", "pytest", "-q"]
    started_at = utc_now()
    started = time.monotonic()
    try:
        completed = _run_pytest_command(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=900,
            env=dict(os.environ),
        )
        return_code = int(completed.returncode)
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as error:
        return_code = 124
        stdout = decode_timeout_stream(error.stdout)
        stderr = decode_timeout_stream(error.stderr) + "\nverified pytest timed out after 900 seconds"
    finished_at = utc_now()
    counts = parse_pytest_counts(stdout + "\n" + stderr)
    record: Dict[str, Any] = {
        "status": "passed" if return_code == 0 else "failed",
        "command": command,
        "command_display": f"{sys.executable} -m pytest -q",
        "return_code": return_code,
        "stdout_sha256": sha256_text(stdout),
        "stderr_sha256": sha256_text(stderr),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_s": round(time.monotonic() - started, 6),
        "collected_test_count": counts["collected"],
        "passed_test_count": counts["passed"],
        "failed_test_count": counts["failed"],
        "skipped_test_count": counts["skipped"],
        "xfailed_test_count": counts["xfailed"],
        "git_commit": commit,
        "git_status_clean": clean_before,
        "source_tree_sha256": source_hash,
        "python_executable": sys.executable,
        "python_version": sys.version,
        "pytest_version": pytest.__version__,
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def validate_test_provenance(
    records: Sequence[Mapping[str, Any]],
    current_commit: str,
    locked_source_hash: str,
) -> Dict[str, Any]:
    checks = []
    for record in records:
        checks.append(
            bool(
                int(record.get("return_code", -1)) == 0
                and record.get("status") == "passed"
                and bool(record.get("git_status_clean"))
                and str(record.get("git_commit")) == str(current_commit)
                and str(record.get("source_tree_sha256")) == str(locked_source_hash)
            )
        )
    return {
        "record_count": len(records),
        "all_valid": len(records) == 2 and all(checks),
        "record_checks": checks,
    }


def parse_pytest_counts(text: str) -> Dict[str, int]:
    names = ["passed", "failed", "skipped", "xfailed"]
    values = {name: last_count(text, name) for name in names}
    collected = sum(values.values())
    explicit = re.findall(r"collected\s+(\d+)\s+items", text)
    if explicit:
        collected = int(explicit[-1])
    values["collected"] = collected
    return values


def last_count(text: str, name: str) -> int:
    matches = re.findall(rf"(\d+)\s+{name}\b", text)
    return int(matches[-1]) if matches else 0


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def decode_timeout_stream(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
