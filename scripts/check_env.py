#!/usr/bin/env python3
"""Check the reproducible detector-prototype environment.

The script verifies required Python packages, repository layout, random seed
configuration, git commit availability, and whether result directories are
writable. It writes a JSON manifest so later reports can cite an exact output
path instead of relying only on terminal text.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import random
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_PACKAGES = {
    "numpy": ("numpy", "numpy"),
    "scipy": ("scipy", "scipy"),
    "pandas": ("pandas", "pandas"),
    "matplotlib": ("matplotlib", "matplotlib"),
    "pyyaml": ("yaml", "PyYAML"),
    "pytest": ("pytest", "pytest"),
    "tqdm": ("tqdm", "tqdm"),
}

REQUIRED_DIRS = [
    "docs",
    "src/degen_detector",
    "src/minibench",
    "src/eval",
    "configs/minibench",
    "configs/detector",
    "scripts",
    "tests",
    "reports",
]

RANDOM_SEED = 42


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run_git(args: list[str], root: Path) -> str | None:
    try:
        output = subprocess.check_output(
            ["git", *args],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return output.strip()


def file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_packages() -> tuple[dict[str, dict[str, str | bool]], list[str]]:
    results: dict[str, dict[str, str | bool]] = {}
    missing: list[str] = []
    for requirement_name, (import_name, distribution_name) in REQUIRED_PACKAGES.items():
        entry: dict[str, str | bool] = {
            "import_name": import_name,
            "distribution_name": distribution_name,
            "available": False,
            "version": "missing",
        }
        try:
            importlib.import_module(import_name)
            entry["available"] = True
            try:
                entry["version"] = importlib.metadata.version(distribution_name)
            except importlib.metadata.PackageNotFoundError:
                entry["version"] = "unknown"
        except ImportError:
            missing.append(requirement_name)
        results[requirement_name] = entry
    return results, missing


def check_writable(path: Path) -> bool:
    path.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(dir=path, prefix=".write_check_", delete=True) as handle:
            handle.write(b"ok")
            handle.flush()
        return True
    except OSError:
        return False


def make_manifest(root: Path) -> tuple[dict[str, Any], list[str]]:
    package_results, missing_packages = check_packages()
    missing_dirs = [directory for directory in REQUIRED_DIRS if not (root / directory).is_dir()]
    manifests_dir = root / "results/environment"
    report_dir = root / "reports"

    random.seed(RANDOM_SEED)
    numpy_seed_probe = None
    try:
        import numpy as np

        np.random.seed(RANDOM_SEED)
        numpy_seed_probe = float(np.random.default_rng(RANDOM_SEED).random())
    except ImportError:
        pass

    manifest: dict[str, Any] = {
        "check_name": "detector_environment_check",
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(root),
        "cwd": os.getcwd(),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "random_seed": RANDOM_SEED,
        "python_random_probe": random.Random(RANDOM_SEED).random(),
        "numpy_random_probe": numpy_seed_probe,
        "git_commit": run_git(["rev-parse", "--short", "HEAD"], root),
        "git_status_short": run_git(["status", "--short"], root),
        "requirements_sha256": file_sha256(root / "requirements.txt"),
        "odi_default_sha256": file_sha256(root / "configs/detector/odi_default.yaml"),
        "packages": package_results,
        "missing_packages": missing_packages,
        "required_dirs": {directory: (root / directory).is_dir() for directory in REQUIRED_DIRS},
        "missing_dirs": missing_dirs,
        "writable_paths": {
            "results/environment": check_writable(manifests_dir),
            "reports": check_writable(report_dir),
        },
    }
    errors: list[str] = []
    if missing_packages:
        errors.append("missing packages: " + ", ".join(missing_packages))
    if missing_dirs:
        errors.append("missing directories: " + ", ".join(missing_dirs))
    for path_name, writable in manifest["writable_paths"].items():
        if not writable:
            errors.append(f"not writable: {path_name}")
    return manifest, errors


def main() -> int:
    root = repo_root()
    manifest, errors = make_manifest(root)
    out_path = root / "results/environment/env_check.json"
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("Degen-LIO detector environment check")
    print(f"repo_root: {root}")
    print(f"git_commit: {manifest['git_commit']}")
    print(f"random_seed: {manifest['random_seed']}")
    print(f"manifest: {out_path}")
    if errors:
        print("status: FAIL")
        for error in errors:
            print(f"error: {error}")
        print("install hint: python -m pip install -r requirements.txt")
        return 1
    print("status: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
