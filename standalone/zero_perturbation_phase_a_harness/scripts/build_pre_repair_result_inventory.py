#!/usr/bin/env python3
"""Build the immutable pre-repair evidence inventory for the survival audit."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = ROOT / "results" / "full_synthetic_development_v1"
OUTPUT = (
    ROOT
    / "artifacts"
    / "scientific_survival_audit_v1"
    / "pre_repair_result_inventory.csv"
)
EXTERNAL_EVIDENCE = (
    "frozen_assets/full_synthetic_development_combined_snapshots_v1.csv",
    "frozen_assets/full_synthetic_development_combined_trials_v1.csv",
    "frozen_assets/full_synthetic_development_protocol_v1.json",
    "docs/full_synthetic_development_protocol_v1.md",
    "frozen_assets/full_synthetic_development_manifest_v1.json",
    "frozen_assets/full_synthetic_development_snapshot_lock_v1.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def semantic_role(relative_path: str) -> str:
    name = Path(relative_path).name
    if "/raw_results/" in f"/{relative_path}":
        return "raw_trial_result"
    exact = {
        "raw_result_manifest.json": "raw_result_inventory",
        "run_manifest.json": "formal_run_manifest",
        "primary_analysis.json": "frozen_primary_analysis",
        "independent_verification.json": "frozen_independent_verification",
        "attempt_events.ndjson": "formal_attempt_event_log",
        "common_association_metrics.json": "frozen_common_association_metrics",
        "phase_b_subset_reproduction.json": "phase_b_subset_reproduction_evidence",
        "full_synthetic_development_combined_snapshots_v1.csv": "snapshot_inventory",
        "full_synthetic_development_combined_trials_v1.csv": "trial_inventory",
        "full_synthetic_development_protocol_v1.json": "development_protocol",
        "full_synthetic_development_protocol_v1.md": "development_protocol_documentation",
        "full_synthetic_development_manifest_v1.json": "development_manifest",
        "full_synthetic_development_snapshot_lock_v1.json": "snapshot_lock",
    }
    try:
        return exact[name]
    except KeyError as exc:
        raise ValueError(f"unclassified evidence file: {relative_path}") from exc


def main() -> None:
    if not RESULT_ROOT.is_dir():
        raise FileNotFoundError(RESULT_ROOT)
    paths = sorted(path for path in RESULT_ROOT.rglob("*") if path.is_file())
    paths.extend(ROOT / relative for relative in EXTERNAL_EVIDENCE)
    if any(not path.is_file() for path in paths):
        missing = [str(path) for path in paths if not path.is_file()]
        raise FileNotFoundError(f"missing evidence: {missing}")
    relative_paths = [path.relative_to(ROOT).as_posix() for path in paths]
    if len(relative_paths) != len(set(relative_paths)):
        raise ValueError("duplicate evidence path")
    rows = [
        {
            "relative_path": relative,
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
            "semantic_role": semantic_role(relative),
        }
        for path, relative in sorted(zip(paths, relative_paths), key=lambda item: item[1])
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("relative_path", "size_bytes", "sha256", "semantic_role"),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"{OUTPUT.relative_to(ROOT)} rows={len(rows)} sha256={sha256(OUTPUT)}")


if __name__ == "__main__":
    main()
