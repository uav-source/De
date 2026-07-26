"""Absolute path contract for Day 5 runtime execution."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RuntimePathError(ValueError):
    """A runtime path violates the fail-closed absolute-path contract."""


def resolve_runtime_path(value: str | Path, *, name: str) -> Path:
    raw = os.fspath(value)
    if not raw.strip():
        raise RuntimePathError(f"{name} must not be empty")
    return Path(raw).expanduser().resolve(strict=False)


def assert_absolute(path: Path, *, name: str) -> Path:
    if not path.is_absolute():
        raise RuntimePathError(f"{name} is not absolute: {path}")
    return path


def duplicated_run_root(run_root: Path, candidate: Path) -> bool:
    text = candidate.as_posix()
    root = run_root.as_posix().rstrip("/")
    return bool(root and text.count(root) > 1)


@dataclass(frozen=True)
class RuntimePaths:
    run_root: Path
    phase_root: Path
    run_dir: Path
    ros_home: Path
    ros_log_dir: Path
    runtime_output_dir: Path
    handshake_output_dir: Path
    source_lock_dir: Path
    runtime_output_inventory_dir: Path
    clip_path: Path
    launch_path: Path
    binary_path: Path
    summary_path: Path
    runtime_binary_path: Path

    def audit(self) -> dict[str, Any]:
        values = {
            name: value
            for name, value in vars(self).items()
            if isinstance(value, Path)
        }
        all_absolute = all(value.is_absolute() for value in values.values())
        duplicate = any(
            duplicated_run_root(self.run_root, value) for value in values.values()
        )
        return {
            "runtime_output_dir_alias": "$RUN_DIR",
            "runtime_output_dir_is_absolute": self.runtime_output_dir.is_absolute(),
            "runtime_output_dir_resolved": str(self.runtime_output_dir),
            "all_runtime_paths_absolute": all_absolute,
            "duplicate_run_root_detected": duplicate,
            "paths": {name: str(value) for name, value in sorted(values.items())},
        }

    def validate(self) -> None:
        audit = self.audit()
        if not audit["all_runtime_paths_absolute"]:
            raise RuntimePathError("one or more runtime paths are not absolute")
        if audit["duplicate_run_root_detected"]:
            raise RuntimePathError("duplicated run-root detected")
        try:
            self.runtime_output_dir.relative_to(self.ros_home)
            nested_in_ros_home = True
        except ValueError:
            nested_in_ros_home = False
        if nested_in_ros_home:
            raise RuntimePathError("runtime output directory is nested below ROS_HOME")


def build_runtime_paths(
    *,
    run_root: str | Path,
    phase_root: str | Path,
    run_dir: str | Path,
    clip_path: str | Path,
    binary_path: str | Path,
) -> RuntimePaths:
    resolved_run_root = resolve_runtime_path(run_root, name="run_root")
    resolved_phase_root = resolve_runtime_path(phase_root, name="phase_root")
    resolved_run_dir = resolve_runtime_path(run_dir, name="run_dir")
    value = RuntimePaths(
        run_root=resolved_run_root,
        phase_root=resolved_phase_root,
        run_dir=resolved_run_dir,
        ros_home=(resolved_run_dir / "ros_home").resolve(strict=False),
        ros_log_dir=(resolved_run_dir / "ros_log").resolve(strict=False),
        runtime_output_dir=resolved_run_dir,
        handshake_output_dir=resolved_run_dir,
        source_lock_dir=(resolved_run_root / "source_locks").resolve(strict=False),
        runtime_output_inventory_dir=resolved_run_dir,
        clip_path=resolve_runtime_path(clip_path, name="clip_path"),
        launch_path=(resolved_run_dir / "day5_startup_sync_v3.launch").resolve(strict=False),
        binary_path=resolve_runtime_path(binary_path, name="binary_path"),
        summary_path=(resolved_run_dir / "run_summary.json").resolve(strict=False),
        runtime_binary_path=(resolved_run_dir / "runtime_audit_v2.bin").resolve(strict=False),
    )
    value.validate()
    return value


def validate_runtime_output_param(expected: Path, actual: str) -> dict[str, Any]:
    if not actual.strip():
        raise RuntimePathError("runtime output rosparam is empty")
    resolved = resolve_runtime_path(actual, name="runtime_output_rosparam")
    if actual != str(expected) or resolved != expected:
        raise RuntimePathError(
            f"runtime output rosparam mismatch: expected {expected}, got {actual}"
        )
    return {
        "runtime_output_param_value": actual,
        "runtime_output_param_is_absolute": resolved.is_absolute(),
        "runtime_output_param_match": True,
    }
