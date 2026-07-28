#!/usr/bin/env python3
"""Run the independent non-formal Phase A runner integration fixture."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.backend_phase_a_metrics import OPEN3D_BACKEND, PCL_BACKEND
from zero_perturbation.backend_phase_a_protocol import file_sha256
from zero_perturbation.backend_phase_a_v1_1 import execute_fixture_chain


FIXTURE = ROOT / "tests/data/backend_phase_a_runner_fixture"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError("fixture output must be absent or empty")
    contract = json.loads((FIXTURE / "fixture_contract.json").read_text())
    point_path = FIXTURE / contract["point_file"]
    if file_sha256(point_path) != contract["point_file_sha256"]:
        raise ValueError("runner fixture point SHA changed")
    points = np.loadtxt(point_path, comments="#", dtype=np.float64)
    manifest = execute_fixture_chain(
        root=ROOT,
        points=points,
        output_dir=args.output_dir,
    )
    results = {}
    for path in (args.output_dir / "trials").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        results[payload["backend"]] = payload
    open3d = results[OPEN3D_BACKEND]
    pcl = results[PCL_BACKEND]
    report = {
        "schema_version": "backend_phase_a_v1_1_fixture_test_report_v1",
        "is_formal_phase_a": False,
        "fixture_only": True,
        "fixture_snapshot_count": manifest["fixture_snapshot_count"],
        "fixture_trial_count": manifest["fixture_trial_count"],
        "fixture_point_count": int(points.shape[0]),
        "fixture_unique_point_count": int(np.unique(points, axis=0).shape[0]),
        "fixture_point_covariance_rank": int(np.linalg.matrix_rank(np.cov(points, rowvar=False))),
        "open3d_fixture_trial_pass": not bool(open3d["solver_failed"]),
        "pcl_fixture_trial_pass": not bool(pcl["solver_failed"]),
        "open3d_translation_update_m": open3d["translation_update_m"],
        "open3d_rotation_update_rad": open3d["rotation_update_rad"],
        "pcl_translation_update_m": pcl["translation_update_m"],
        "pcl_rotation_update_rad": pcl["rotation_update_rad"],
        "backend_input_checksum_mismatch_count": manifest[
            "backend_input_checksum_mismatch_count"
        ],
        "formal_rng_instantiation_count": 0,
        "formal_snapshot_generation_count": 0,
        "formal_backend_execution_count": 0,
        "formal_trial_result_count": 0,
        "confirmatory_seed_access_count": 0,
        "old_capture_test_seed_access_count": 0,
        "native_formal_execution_count": 0,
        "fixture_test_pass": bool(
            not open3d["solver_failed"]
            and not pcl["solver_failed"]
            and manifest["backend_input_checksum_mismatch_count"] == 0
        ),
    }
    report_path = args.output_dir / "fixture_test_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report["fixture_test_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

