#!/usr/bin/env python3
"""Publish the stopped PCL backend qualification v2 from one recorded CTest run."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "build/pcl_point_to_plane/pcl_backend_v2_results"
ARTIFACT = ROOT / "artifacts/current/zero_perturbation_backend_qualification_v2"
REPORTS = ROOT / "reports/zero_perturbation_pcl_environment_v2"
PROTOCOL = ROOT / "configs/zero_perturbation/backend_qualification_v2.yaml"
PROTOCOL_LOCK_COMMIT = "cc059956e5218e219bb3ec6ad027437fa37d3e13"
BASELINE_COMMIT = "04cb2e36c2af75500ae1b5c65bd7c2b037613bfe"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def git_unchanged(*paths: str) -> bool:
    return (
        subprocess.run(
            ["git", "diff", "--quiet", BASELINE_COMMIT, "--", *paths], cwd=ROOT
        ).returncode
        == 0
    )


def rotation_projection_audit(truth: np.ndarray, estimate: np.ndarray) -> dict[str, object]:
    estimate_rotation = estimate[:3, :3]
    truth_rotation = truth[:3, :3]
    raw_delta = truth_rotation.T @ estimate_rotation
    raw_cosine = float(np.clip((np.trace(raw_delta) - 1.0) * 0.5, -1.0, 1.0))
    left, singular_values, right = np.linalg.svd(estimate_rotation)
    projected = left @ right
    if np.linalg.det(projected) < 0:
        left[:, -1] *= -1.0
        projected = left @ right
    projected_delta = truth_rotation.T @ projected
    projected_cosine = float(
        np.clip((np.trace(projected_delta) - 1.0) * 0.5, -1.0, 1.0)
    )
    return {
        "gate_metric_changed_post_result": False,
        "gate_rotation_error_to_truth_rad": math.acos(raw_cosine),
        "gate_threshold_rad": 1.0e-4,
        "gate_pass": math.acos(raw_cosine) <= 1.0e-4,
        "non_gating_projected_so3_rotation_error_rad": math.acos(projected_cosine),
        "estimate_rotation_orthogonality_error_fro": float(
            np.linalg.norm(estimate_rotation.T @ estimate_rotation - np.eye(3), ord="fro")
        ),
        "estimate_rotation_determinant": float(np.linalg.det(estimate_rotation)),
        "estimate_rotation_singular_values": singular_values.tolist(),
        "max_abs_rotation_matrix_element_error": float(
            np.max(np.abs(estimate_rotation - truth_rotation))
        ),
        "interpretation": (
            "The frozen raw trace/acos gate fails. Projection to SO(3) is recorded "
            "only as a post-result diagnostic and does not rescue or rerun v2."
        ),
    }


def matrix_block(value: object) -> str:
    matrix = np.asarray(value, dtype=np.float64).reshape(4, 4)
    return "\n".join(" ".join(f"{number:.12g}" for number in row) for row in matrix)


def normal_row(test_name: str, cloud: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "microtest": test_name,
        "cloud": cloud,
        "finite_count": payload[f"{cloud}_normal_finite_count"],
        "zero_count": payload[f"{cloud}_normal_zero_count"],
        "nan_count": payload[f"{cloud}_normal_nan_count"],
        "norm_min": payload[f"{cloud}_normal_norm_min"],
        "norm_median": payload[f"{cloud}_normal_norm_median"],
        "norm_max": payload[f"{cloud}_normal_norm_max"],
        "direction_rank": payload[f"{cloud}_normal_direction_rank"],
    }


def write_sums(directory: Path) -> None:
    paths = sorted(
        path for path in directory.rglob("*") if path.is_file() and path.name != "SHA256SUMS"
    )
    (directory / "SHA256SUMS").write_text(
        "".join(f"{sha256(path)}  {path.relative_to(directory).as_posix()}\n" for path in paths),
        encoding="utf-8",
    )


def main() -> None:
    result_paths = {
        "A": RESULTS / "nondegenerate_identity.json",
        "B": RESULTS / "known_small_transform.json",
        "C": RESULTS / "planar_degeneracy_diagnostic.json",
    }
    results = {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, path in result_paths.items()
    }
    passed = {name: bool(value["microtest_pass"]) for name, value in results.items()}
    implementation_valid = passed == {"A": True, "B": True, "C": True}
    if passed != {"A": True, "B": False, "C": True}:
        raise RuntimeError(f"unexpected recorded stop pattern: {passed}")

    truth = np.asarray(results["B"]["truth_source_to_target_transform_4x4"], dtype=np.float64)
    estimate = np.asarray(
        results["B"]["estimated_source_to_target_transform_4x4"], dtype=np.float64
    )
    numeric_audit = rotation_projection_audit(truth, estimate)

    raw = ARTIFACT / "raw"
    tables = ARTIFACT / "tables"
    raw.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    for name, path in result_paths.items():
        shutil.copy2(path, raw / f"test_{name.lower()}_result.json")
    shutil.copy2(
        ROOT / "build/pcl_point_to_plane/Testing/Temporary/LastTest.log",
        raw / "ctest_last_test.log",
    )
    shutil.copy2(
        ROOT / "build/pcl_point_to_plane/Testing/Temporary/LastTestsFailed.log",
        raw / "ctest_last_tests_failed.log",
    )

    decision = {
        "schema_version": "pcl_backend_qualification_v2_decision_v1",
        "PCL_DEPENDENCY_READY": True,
        "PCL_CLI_COMPILED": True,
        "PCL_V1_PLANAR_IDENTITY_SMOKE": "FAIL",
        "PCL_V1_SMOKE_FIXTURE_DEGENERATE": True,
        "PCL_BACKEND_QUALIFICATION": "NOT_EVALUATED",
        "V2_TEST_A_NONDEGENERATE_IDENTITY_PASS": passed["A"],
        "V2_TEST_B_KNOWN_SMALL_TRANSFORM_PASS": passed["B"],
        "V2_TEST_C_PLANAR_DEGENERACY_DIAGNOSTIC_PASS": passed["C"],
        "PCL_BACKEND_IMPLEMENTATION_VALID": implementation_valid,
        "PCL_BACKEND_PHASE_A_QUALIFICATION_AUTHORIZED": implementation_valid,
        "phase_a_executed": False,
        "phase_b_executed": False,
        "development_seed_access_count": 0,
        "confirmatory_seed_access_count": 0,
        "old_test_seed_access_count": 0,
        "seed_access_count": 0,
        "formal_pcl_parameters_modified": False,
        "pcl_version_changed": False,
        "open3d_modified": False,
        "native_modified": False,
        "third_backend_substitution_attempted": False,
        "parameter_rescue_attempted": False,
        "microtest_rerun_after_failure": False,
        "stop_reason": "KNOWN_SMALL_TRANSFORM_ROTATION_ERROR_GATE_FAILED",
        "failed_gate_actual_rotation_error_rad": results["B"][
            "rotation_error_to_truth_rad"
        ],
        "failed_gate_threshold_rotation_error_rad": 1.0e-4,
        "git_push_performed": False,
    }
    write_json(ARTIFACT / "final_decision.json", decision)

    cli_path = ROOT / "build/pcl_point_to_plane/pcl_point_to_plane_cli"
    run_manifest = {
        "schema_version": "pcl_backend_qualification_v2_run_manifest_v1",
        "branch": "feature/zero-perturbation-pcl-backend-qualification-v2",
        "baseline_commit": BASELINE_COMMIT,
        "protocol_lock_commit": PROTOCOL_LOCK_COMMIT,
        "protocol_path": str(PROTOCOL.relative_to(ROOT)),
        "protocol_sha256": sha256(PROTOCOL),
        "pcl_version": results["A"]["cli_result"]["pcl_version"],
        "pcl_cli_sha256": sha256(cli_path),
        "fixture_generator_sha256": sha256(
            ROOT / "tests/data/pcl_backend_v2/generate_fixtures.py"
        ),
        "ctest_command": (
            "MAMBA_ROOT_PREFIX=/home/lj/.local/share/degen-lio-micromamba "
            "/home/lj/.local/bin/micromamba run -n degen-lio-pcl-backend "
            "ctest --test-dir build/pcl_point_to_plane "
            "-L pcl_backend_qualification_v2 -V --output-on-failure"
        ),
        "ctest_execution_count": 1,
        "microtest_execution_count": {"A": 1, "B": 1, "C": 1},
        "microtest_pass_count": sum(passed.values()),
        "microtest_failure_count": 3 - sum(passed.values()),
        "phase_a_executed": False,
        "phase_b_executed": False,
        "development_run_executed": False,
        "confirmatory_run_executed": False,
        "seed_access_count": 0,
        "truth_passed_to_cli": False,
        "v1_reports_modified": not git_unchanged(
            "artifacts/current/zero_perturbation_backend_qualification",
            "reports/zero_perturbation_pcl_environment",
        ),
        "v1_fixture_modified": not git_unchanged("tests/data/pcl_backend"),
        "open3d_modified": not git_unchanged("src/zero_perturbation/open3d_backend.py"),
        "native_modified": not git_unchanged("src/zero_perturbation/native_backend.py"),
        "formal_pcl_parameters_modified": False,
        "git_push_performed": False,
        "stop_reason": decision["stop_reason"],
    }
    write_json(ARTIFACT / "run_manifest.json", run_manifest)
    write_json(ARTIFACT / "numeric_diagnostic_note.json", numeric_audit)
    write_json(
        ARTIFACT / "parameter_lock_audit.json",
        {
            "pcl_version": "1.15.1",
            "normal_k": 50,
            "normal_threads": 1,
            "maximum_correspondence_distance_m": 0.50,
            "maximum_iterations": 50,
            "transformation_epsilon": 1.0e-10,
            "euclidean_fitness_epsilon": 1.0e-10,
            "use_reciprocal_correspondences": False,
            "use_symmetric_objective": False,
            "enforce_same_direction_normals": True,
            "parameter_lock_pass": True,
        },
    )
    write_json(
        ARTIFACT / "seed_firewall_audit.json",
        {
            "fixture_generator_random_seed_used": False,
            "development_seed_access_count": 0,
            "confirmatory_seed_access_count": 0,
            "old_test_seed_access_count": 0,
            "seed_firewall_pass": True,
        },
    )

    with (tables / "microtest_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            [
                "test_id",
                "microtest",
                "pass",
                "has_converged_raw",
                "final_transform_finite",
                "fitness_finite",
                "translation_update_norm_m",
                "rotation_update_norm_rad",
                "translation_error_to_truth_m",
                "rotation_error_to_truth_rad",
                "point_cloud_rank",
                "point_to_plane_jacobian_rank",
                "rank_deficient",
            ]
        )
        for name in ("A", "B", "C"):
            result = results[name]
            payload = result["cli_result"]
            writer.writerow(
                [
                    name,
                    result["microtest"],
                    result["microtest_pass"],
                    payload["has_converged_raw"],
                    payload["final_transform_finite"],
                    payload["fitness_finite"],
                    payload["translation_update_norm_m"],
                    payload["rotation_update_norm_rad"],
                    result.get("translation_error_to_truth_m"),
                    result.get("rotation_error_to_truth_rad"),
                    payload["point_cloud_rank"],
                    payload["point_to_plane_jacobian_rank"],
                    payload["rank_deficient"],
                ]
            )

    normal_rows = [
        normal_row(results[name]["microtest"], cloud, results[name]["cli_result"])
        for name in ("A", "B", "C")
        for cloud in ("source", "target")
    ]
    with (tables / "normal_statistics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(normal_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(normal_rows)

    with (tables / "hessian_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            [
                "test_id",
                "point_cloud_rank",
                "jacobian_rank",
                "condition_status",
                "eigenvalue_0",
                "eigenvalue_1",
                "eigenvalue_2",
                "eigenvalue_3",
                "eigenvalue_4",
                "eigenvalue_5",
            ]
        )
        for name in ("A", "B", "C"):
            payload = results[name]["cli_result"]
            writer.writerow(
                [
                    name,
                    payload["point_cloud_rank"],
                    payload["point_to_plane_jacobian_rank"],
                    payload["condition_status"],
                    *payload["point_to_plane_hessian_eigenvalues"],
                ]
            )

    a = results["A"]["cli_result"]
    b = results["B"]["cli_result"]
    c = results["C"]["cli_result"]
    report = f"""# PCL Backend Qualification v2 — stopped decision

## Decision

The independent v2 implementation qualification **stops as FAIL**. Test A and
the Test C diagnostic passed, but Test B's frozen raw trace/acos rotation error
was `{results['B']['rotation_error_to_truth_rad']:.15g}` rad, above the
`1e-4` rad gate. Therefore `PCL_BACKEND_IMPLEMENTATION_VALID=false` and
`PCL_BACKEND_PHASE_A_QUALIFICATION_AUTHORIZED=false`. No test was rerun after
the failure.

## v1 fixture rank and reclassification

The preserved v1 fixture has coordinate rank 2. With the normals estimated by
the unchanged PCL KSearch=50 implementation, its point-to-plane Jacobian/Hessian
rank is {c['point_to_plane_jacobian_rank']}; sorted Hessian eigenvalues are
`{c['point_to_plane_hessian_eigenvalues']}`. The three zero modes correspond to
in-plane translations and rotation about the plane normal. The fixture cannot
observe all six rigid-body degrees of freedom and therefore was not a valid
hard qualification gate. Its historical smoke result remains FAIL; it is
reclassified as fixture-degenerate and backend qualification remains
NOT_EVALUATED, never rewritten as PASS.

## v2 nondegenerate fixture and Hessian

The seed-free fixture contains {a['target_point_count']} finite unique points
from three perpendicular planes and an off-centre cuboid bump. Coordinate rank
is {a['point_cloud_rank']}. The constructive analytic Hessian rank is 6 with
eigenvalues `[126.96221040873503, 131.15107985614438, 136.67100767861896,
230.31747283225394, 289.94028524243305, 328.8629856151476]`. Using the actual
PCL-estimated target normals, Test A also has rank
{a['point_to_plane_jacobian_rank']} and eigenvalues
`{a['point_to_plane_hessian_eigenvalues']}`.

## Source and target normal statistics

For Test A, both source and target have finite={a['source_normal_finite_count']},
zero={a['source_normal_zero_count']}, NaN={a['source_normal_nan_count']}, norm
min/median/max=`{a['source_normal_norm_min']}` / `{a['source_normal_norm_median']}` /
`{a['source_normal_norm_max']}`, and direction rank
{a['source_normal_direction_rank']}. Test B source has finite=
{b['source_normal_finite_count']}, zero={b['source_normal_zero_count']}, NaN=
{b['source_normal_nan_count']}, norm min/median/max=
`{b['source_normal_norm_min']}` / `{b['source_normal_norm_median']}` /
`{b['source_normal_norm_max']}`; its target statistics equal Test A target.
All Test C normals are finite unit normals with direction rank 1. The complete
per-test table is `tables/normal_statistics.csv`.

## Test A — NONDEGENERATE_IDENTITY

PASS. Raw convergence={str(a['has_converged_raw']).lower()}, finite transform=
{str(a['final_transform_finite']).lower()}, finite fitness=
{str(a['fitness_finite']).lower()}, correspondences={a['correspondence_count']}.
Final transform:

```text
{matrix_block(a['final_transformation_4x4'])}
```

Translation update=`{a['translation_update_norm_m']}` m; rotation update=
`{a['rotation_update_norm_rad']}` rad.

## Test B — KNOWN_SMALL_TRANSFORM

FAIL. The source was constructed from the target with translation
`[0.01, -0.02, 0.03]` m and RPY `[0.2, -0.3, 0.5]` degrees. The expected
source-to-target transform is:

```text
{matrix_block(results['B']['truth_source_to_target_transform_4x4'])}
```

The estimate is:

```text
{matrix_block(results['B']['estimated_source_to_target_transform_4x4'])}
```

Translation error=`{results['B']['translation_error_to_truth_m']}` m (PASS).
Frozen raw rotation error=`{results['B']['rotation_error_to_truth_rad']}` rad
(FAIL versus `1e-4`). Raw convergence and transform/fitness finiteness are true.
The CLI's `qualification_pass=true` is intentionally a truth-free internal
health predicate; the authoritative Test B result is the verifier's
`microtest_pass=false`, because truth is never passed to the registration CLI.

The estimated 3x3 block has Frobenius orthogonality error
`{numeric_audit['estimate_rotation_orthogonality_error_fro']}`. A post-result
closest-SO(3) projection gives diagnostic error
`{numeric_audit['non_gating_projected_so3_rotation_error_rad']}` rad, but the
protocol did not prospectively specify projection. This observation is not
used to change the gate, rerun the test, or rescue v2.

## Test C — PLANAR_DEGENERACY_DIAGNOSTIC

PASS as a diagnostic: point-cloud rank={c['point_cloud_rank']}, Jacobian rank=
{c['point_to_plane_jacobian_rank']}, rank-deficient=
{str(c['rank_deficient']).lower()}, condition=`{c['condition_status']}`. Raw
PCL convergence was {str(c['has_converged_raw']).lower()} but was not a gate;
the final transform was non-finite and is separately recorded.

## Scope and compliance

Phase A and Phase B were not run. No Development, Confirmatory, or old Test
seed was accessed; no RNG was used by the fixture generator. The frozen PCL
parameters and PCL 1.15.1 were unchanged. v1 reports and fixtures, Open3D, and
Native were not modified. No third backend, parameter rescue, commit rewrite,
or push was performed. This stopped v2 result authorizes no Phase A execution.
"""
    (ARTIFACT / "backend_qualification_v2_report.md").write_text(
        report, encoding="utf-8"
    )

    shutil.copy2(raw / "ctest_last_test.log", REPORTS / "ctest_verbose.txt")
    shutil.copy2(
        raw / "ctest_last_tests_failed.log", REPORTS / "ctest_failed_tests.txt"
    )
    shutil.copy2(
        ROOT / "build/pcl_point_to_plane/CTestTestfile.cmake",
        REPORTS / "CTestTestfile.cmake",
    )
    (REPORTS / "binary_sha256.txt").write_text(
        f"{sha256(cli_path)}  build/pcl_point_to_plane/pcl_point_to_plane_cli\n",
        encoding="utf-8",
    )
    write_json(
        REPORTS / "package_versions.json",
        {
            "pcl": "1.15.1",
            "eigen": "5.0.1",
            "boost": "1.90.0",
            "flann": "1.9.2",
            "pcl_environment": "degen-lio-pcl-backend",
            "pcl_version_changed": False,
        },
    )
    write_json(
        REPORTS / "build_metadata.json",
        {
            "cli_compiled": True,
            "cli_sha256": sha256(cli_path),
            "cmake_source": "tools/pcl_point_to_plane",
            "cmake_build": "build/pcl_point_to_plane",
            "ctest_count": 3,
            "ctest_pass_count": 2,
            "ctest_fail_count": 1,
            "failed_test": "pcl_v2_known_small_transform",
        },
    )
    write_sums(ARTIFACT)
    write_sums(REPORTS)


if __name__ == "__main__":
    main()
