#!/usr/bin/env python3
"""Safely remove only allowlisted generated data and runtime caches.

The command is a dry run unless ``--apply`` is given.  It accepts no arbitrary
path arguments and never follows symbolic links.
"""

from __future__ import annotations

import argparse
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIRS = (
    "data/minibench",
    "data/metric_redesign_stage1",
    "data/metric_redesign_stage1b",
    "data/metric_redesign_stage1c",
    "data/detector_stage2a",
    "data/weak_update_stage2b",
    "results/metric_redesign_stage1",
    "results/metric_redesign_stage1b",
    "results/metric_redesign_stage1c",
    "results/detector_stage2a",
    "results/weak_update_stage2b",
    # Explicit legacy result trees named for removal by the cleanup plan.
    "results/day14",
    "results/day30",
)
PROTECTED_DIRS = (".git", "artifacts/history")


class CleanupSafetyError(RuntimeError):
    """Raised when a candidate is outside the fixed cleanup policy."""


@dataclass(frozen=True)
class CleanupSummary:
    target_count: int
    file_count: int
    byte_count: int
    applied: bool
    deleted_file_count: int
    deleted_bytes: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="delete allowlisted targets")
    return parser.parse_args()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_target(root: Path, target: Path) -> None:
    root = Path(root).resolve()
    lexical = Path(os.path.abspath(target))
    if not is_relative_to(lexical, root):
        raise CleanupSafetyError(f"cleanup target is outside repository: {target}")
    relative = lexical.relative_to(root)
    if not relative.parts:
        raise CleanupSafetyError("repository root cannot be deleted")
    if relative.parts[0] == ".git":
        raise CleanupSafetyError(".git cannot be deleted")
    if relative.parts[:2] == ("artifacts", "history"):
        raise CleanupSafetyError("historical artifacts cannot be deleted")
    if target.is_symlink():
        resolved = target.resolve(strict=False)
        if not is_relative_to(resolved, root):
            raise CleanupSafetyError(f"symbolic link escapes repository: {target} -> {resolved}")
        raise CleanupSafetyError(f"symbolic links are never cleanup targets: {target}")


def matches_runtime_allowlist(relative: Path) -> bool:
    name = relative.name
    return bool(
        name in {"__pycache__", ".pytest_cache"}
        or name.startswith("mplconfig")
        or relative.suffix in {".pyc", ".pyo", ".log"}
    )


def discover_targets(root: Path = ROOT) -> List[Path]:
    root = Path(root).resolve()
    targets: set[Path] = set()
    for relative in GENERATED_DIRS:
        candidate = root / relative
        if candidate.exists() or candidate.is_symlink():
            validate_target(root, candidate)
            targets.add(candidate)

    for directory, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(directory)
        relative_current = current.relative_to(root)
        if relative_current.parts[:1] == (".git",) or relative_current.parts[:2] == ("artifacts", "history"):
            dirnames[:] = []
            continue
        for name in list(dirnames):
            candidate = current / name
            relative = candidate.relative_to(root)
            if candidate.is_symlink() and matches_runtime_allowlist(relative):
                validate_target(root, candidate)
            if matches_runtime_allowlist(relative):
                validate_target(root, candidate)
                targets.add(candidate)
                dirnames.remove(name)
        for name in filenames:
            candidate = current / name
            relative = candidate.relative_to(root)
            if matches_runtime_allowlist(relative):
                validate_target(root, candidate)
                targets.add(candidate)

    ordered = sorted(targets, key=lambda path: (len(path.parts), str(path)))
    minimal: List[Path] = []
    for target in ordered:
        if not any(is_relative_to(target, parent) for parent in minimal):
            minimal.append(target)
    return minimal


def iter_files(target: Path) -> Iterable[Path]:
    if target.is_symlink():
        raise CleanupSafetyError(f"refusing to inspect symbolic link: {target}")
    if target.is_file():
        yield target
        return
    if not target.exists():
        return
    for directory, dirnames, filenames in os.walk(target, topdown=True, followlinks=False):
        current = Path(directory)
        for name in list(dirnames):
            child = current / name
            if child.is_symlink():
                raise CleanupSafetyError(f"refusing symbolic link inside cleanup tree: {child}")
        for name in filenames:
            child = current / name
            if child.is_symlink():
                raise CleanupSafetyError(f"refusing symbolic link inside cleanup tree: {child}")
            yield child


def target_totals(targets: Sequence[Path]) -> tuple[int, int]:
    files = list(file for target in targets for file in iter_files(target))
    return len(files), sum(file.stat().st_size for file in files)


def run_cleanup(root: Path = ROOT, apply: bool = False) -> CleanupSummary:
    root = Path(root).resolve()
    targets = discover_targets(root)
    file_count, byte_count = target_totals(targets)
    print(f"repository root: {root}")
    print("cleanup allowlist:")
    for value in GENERATED_DIRS:
        print(f"  - {value}/")
    print("  - **/__pycache__/; .pytest_cache/; mplconfig*/; **/*.pyc; **/*.pyo; **/*.log")
    print(f"targets: {len(targets)}; files: {file_count}; bytes: {byte_count}")
    for target in targets:
        print(f"{'DELETE' if apply else 'DRY-RUN'} {target.relative_to(root)}")
    if not apply:
        print("dry-run only; rerun with --apply to delete the listed targets")
        return CleanupSummary(len(targets), file_count, byte_count, False, 0, 0)

    for target in sorted(targets, key=lambda path: (len(path.parts), str(path)), reverse=True):
        validate_target(root, target)
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    print(f"deleted files: {file_count}; released bytes: {byte_count}")
    return CleanupSummary(len(targets), file_count, byte_count, True, file_count, byte_count)


def main() -> int:
    args = parse_args()
    run_cleanup(ROOT, apply=bool(args.apply))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
