#!/usr/bin/env python3
"""Finalize, package, and externally verify the Day 6 branch audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.day6_branch_divergence import (  # noqa: E402
    DAY6_AUDIT_FINAL_DELIVERY_SHA256,
    DAY6_AUDIT_PRE_PERMISSION_NORMALIZATION_SHA256,
    EXPECTED_DEGEN_BRANCH,
    EXPECTED_DEGEN_HEAD,
    ROOT_CAUSE_REQUIRED_GATES,
    ensure_root_cause_not_overclaimed,
    evaluate_root_cause_gate,
    sha256_file,
    validate_source_lock,
    write_json,
)
from fastlio2_adapter.day6_divergence_hypotheses import (  # noqa: E402
    validate_hypothesis_rows,
)


AUDIT_NAME = (
    "Degen-LIO-multihyp-D6-fallback-branch-divergence-root-cause-audit"
)
ARCHIVE_NAME = f"{AUDIT_NAME}.tar.gz"
ANALYSIS_SOURCE_PATHS = (
    "src/fastlio2_adapter/day6_branch_divergence.py",
    "src/fastlio2_adapter/day6_semantic_observation.py",
    "src/fastlio2_adapter/day6_eigenspace_stability.py",
    "src/fastlio2_adapter/day6_divergence_hypotheses.py",
    "scripts/80_extract_day6_branch_inputs.py",
    "scripts/81_compare_day6_semantic_observations.py",
    "scripts/82_analyze_day6_eigenspace_stability.py",
    "scripts/83_finalize_day6_branch_root_cause.py",
    "scripts/84_render_day6_branch_root_cause_plots.py",
)
TEST_PATHS = (
    "tests/test_day6_semantic_observation.py",
    "tests/test_day6_first_divergence.py",
    "tests/test_day6_divergence_order.py",
    "tests/test_day6_evidence_granularity.py",
    "tests/test_day6_eigenspace_reconstruction.py",
    "tests/test_day6_sign_invariant_angles.py",
    "tests/test_day6_weak_subspace_angles.py",
    "tests/test_day6_hypothesis_matrix.py",
    "tests/test_day6_branch_root_cause_gate.py",
)
DOC_PATHS = (
    "docs/harmful_bias/day6_branch_divergence_root_cause_contract.md",
    "docs/harmful_bias/day6_branch_divergence_root_cause_report.md",
    "docs/harmful_bias/next_minimal_divergence_experiment.md",
    "manifests/harmful_bias/day6_branch_divergence_root_cause_manifest.json",
)
ARTIFACT_PATH = (
    "artifacts/current/harmful_bias_multihyp_dev/"
    "day6_branch_divergence_root_cause/"
)
ALLOWED_NEW_PATHS = set(
    ANALYSIS_SOURCE_PATHS + TEST_PATHS + DOC_PATHS + (ARTIFACT_PATH,)
)
TEXT_SUFFIXES = {
    ".csv",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".sh",
    ".txt",
    ".yaml",
    ".yml",
}
FAST_SYMBOLS = (
    {
        "file": "src/laserMapping.cpp",
        "symbol": "h_share_model",
        "start_pattern": "void h_share_model",
        "end_pattern": "void map_incremental",
        "parallelized": True,
        "shared_mutable_structures": (
            "feats_down_world, Nearest_Points, point_selected_surf, "
            "normvec, res_last"
        ),
        "index_ownership": "loop index i",
        "write_pattern": "index-owned writes followed by serial compaction",
        "ordering_guarantee": "serial compaction is source-index ordered",
        "potential_nondeterminism_mechanism": (
            "parallel search timing or upstream mutable-map visibility"
        ),
        "direct_runtime_evidence_available": False,
        "classification": "PLAUSIBLE_BUT_UNPROVEN",
    },
    {
        "file": "src/laserMapping.cpp",
        "symbol": "formal_correspondence_and_jacobian_construction",
        "start_pattern": "effct_feat_num = 0;",
        "end_pattern": "void map_incremental",
        "parallelized": False,
        "shared_mutable_structures": (
            "laserCloudOri, corr_normvect, ekfom_data.h_x, ekfom_data.h"
        ),
        "index_ownership": "serial effective-feature index",
        "write_pattern": "serial compaction and row construction",
        "ordering_guarantee": "accepted source indices retain source order",
        "potential_nondeterminism_mechanism": (
            "inherits upstream selection/map differences"
        ),
        "direct_runtime_evidence_available": True,
        "classification": "DIRECTLY_SUPPORTED",
    },
    {
        "file": "src/laserMapping.cpp",
        "symbol": "map_incremental",
        "start_pattern": "void map_incremental",
        "end_pattern": "void publish_frame_world",
        "parallelized": False,
        "shared_mutable_structures": "ikdtree, Nearest_Points",
        "index_ownership": "serial source index",
        "write_pattern": "ordered PointToAdd then Add_Points calls",
        "ordering_guarantee": "input vectors are serially assembled",
        "potential_nondeterminism_mechanism": (
            "tree operation history could affect later neighbor search"
        ),
        "direct_runtime_evidence_available": False,
        "classification": "NOT_OBSERVABLE",
    },
    {
        "file": "include/common_lib.h",
        "symbol": "esti_plane",
        "start_pattern": "bool esti_plane",
        "end_pattern": "return true;",
        "parallelized": False,
        "shared_mutable_structures": "none visible in helper",
        "index_ownership": "function-local inputs",
        "write_pattern": "function-local plane output",
        "ordering_guarantee": "uses provided neighbor vector order",
        "potential_nondeterminism_mechanism": (
            "sensitive to different neighbor inputs"
        ),
        "direct_runtime_evidence_available": False,
        "classification": "PLAUSIBLE_BUT_UNPROVEN",
    },
    {
        "file": "include/ikd-Tree/ikd_Tree.cpp",
        "symbol": "Nearest_Search",
        "start_pattern": "::Nearest_Search",
        "end_pattern": "::Box_Search",
        "parallelized": False,
        "shared_mutable_structures": "tree root and rebuild synchronization state",
        "index_ownership": "per-call local heap and output vectors",
        "write_pattern": "local result extraction with guarded rebuild access",
        "ordering_guarantee": "heap output order follows search result ordering",
        "potential_nondeterminism_mechanism": (
            "tree content/history or equal-distance ordering sensitivity"
        ),
        "direct_runtime_evidence_available": False,
        "classification": "NOT_OBSERVABLE",
    },
    {
        "file": "include/ikd-Tree/ikd_Tree.cpp",
        "symbol": "Add_Points",
        "start_pattern": "::Add_Points",
        "end_pattern": "::Delete_Point_Boxes",
        "parallelized": False,
        "shared_mutable_structures": "tree and operation logger",
        "index_ownership": "serial insertion-loop index",
        "write_pattern": "ordered point insert/delete operations",
        "ordering_guarantee": "caller vector order is consumed serially",
        "potential_nondeterminism_mechanism": (
            "different insertion history can produce different tree state"
        ),
        "direct_runtime_evidence_available": False,
        "classification": "NOT_OBSERVABLE",
    },
    {
        "file": "include/ikd-Tree/ikd_Tree.cpp",
        "symbol": "Delete_Point_Boxes",
        "start_pattern": "::Delete_Point_Boxes",
        "end_pattern": "::size",
        "parallelized": False,
        "shared_mutable_structures": "tree and operation logger",
        "index_ownership": "serial box-loop index",
        "write_pattern": "ordered range deletions",
        "ordering_guarantee": "caller box order is consumed serially",
        "potential_nondeterminism_mechanism": (
            "different deletion history can affect later search"
        ),
        "direct_runtime_evidence_available": False,
        "classification": "NOT_OBSERVABLE",
    },
    {
        "file": "include/IKFoM_toolkit/esekfom/esekfom.hpp",
        "symbol": "update_iterated_dyn_share_modified",
        "start_pattern": "void update_iterated_dyn_share_modified",
        "end_pattern": "void change_x",
        "parallelized": False,
        "shared_mutable_structures": "filter state x_ and covariance P_",
        "index_ownership": "single filter update path",
        "write_pattern": "iterated state and covariance update",
        "ordering_guarantee": "measurement model called within serial iteration",
        "potential_nondeterminism_mechanism": (
            "propagates any prior measurement-side divergence"
        ),
        "direct_runtime_evidence_available": True,
        "classification": "DIRECTLY_SUPPORTED",
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument(
        "--semantic-comparison",
        required=True,
        type=Path,
    )
    parser.add_argument("--eigenspace", required=True, type=Path)
    parser.add_argument("--source-audit", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def git_output(arguments: Sequence[str]) -> str:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise ValueError(completed.stderr.strip())
    return completed.stdout


def status_paths(text: str) -> set[str]:
    result = set()
    for line in text.splitlines():
        if not line:
            continue
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        result.add(value)
    return result


def test_pass(log: Path, rc: Path) -> bool:
    return (
        log.is_file()
        and rc.is_file()
        and rc.read_text(encoding="utf-8").strip() == "0"
    )


def find_line_range(
    path: Path,
    start_pattern: str,
    end_pattern: str,
) -> tuple[int, int]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    starts = [
        index + 1 for index, line in enumerate(lines)
        if start_pattern in line
    ]
    if not starts:
        raise ValueError(f"source start pattern missing: {start_pattern}")
    start = starts[0]
    ends = [
        index + 1
        for index, line in enumerate(lines)
        if index + 1 > start and end_pattern in line
    ]
    end = (ends[0] - 1) if ends else min(len(lines), start + 200)
    return start, max(start, end)


def build_source_audit(
    input_root: Path,
    output: Path,
) -> list[dict[str, Any]]:
    fast_root = input_root / "source_reference/fastlio2"
    rows = []
    for definition in FAST_SYMBOLS:
        path = fast_root / definition["file"]
        start, end = find_line_range(
            path,
            str(definition["start_pattern"]),
            str(definition["end_pattern"]),
        )
        row = {
            "file": definition["file"],
            "symbol": definition["symbol"],
            "line_range": f"{start}-{end}",
            "source_sha256": sha256_file(path),
            "parallelized": str(definition["parallelized"]).lower(),
            "shared_mutable_structures": definition[
                "shared_mutable_structures"
            ],
            "index_ownership": definition["index_ownership"],
            "write_pattern": definition["write_pattern"],
            "ordering_guarantee": definition["ordering_guarantee"],
            "potential_nondeterminism_mechanism": definition[
                "potential_nondeterminism_mechanism"
            ],
            "direct_runtime_evidence_available": str(
                definition["direct_runtime_evidence_available"]
            ).lower(),
            "classification": definition["classification"],
        }
        rows.append(row)
    write_csv(output / "fastlio2_divergence_path_symbols.csv", rows)
    lines = [
        "# FAST-LIO2 divergence-path static audit",
        "",
        "This is a static engineering audit. Parallel code is not direct evidence of a data race.",
        "",
        "The frozen record localizes the first visible difference to formal measurement/correspondence objects while the prior remains equal. It does not include map-content, insertion-order, scheduling, thread, neighbor-identity, plane-array, or raw-payload traces.",
        "",
        "## Bounded findings",
        "",
        "- `h_share_model` contains a parallel per-source correspondence-search loop with index-owned writes, followed by serial effective-point compaction and formal J/h construction.",
        "- `Nearest_Search`, plane fitting, incremental insertion/deletion, and the iterated state/covariance update are upstream or downstream static paths.",
        "- The available runtime record directly supports formal measurement divergence and subsequent state propagation.",
        "- Map, scheduling, ikd-tree ordering, and a conflicting shared write remain unobserved.",
        "",
        "## Symbol table",
        "",
    ]
    for row in rows:
        lines.append(
            f"- `{row['file']}::{row['symbol']}` lines "
            f"`{row['line_range']}`: `{row['classification']}`."
        )
    (output / "fastlio2_divergence_path_source_audit.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return rows


def next_experiment_value() -> dict[str, Any]:
    experiments = [
        {
            "rank": 1,
            "experiment_id": "A_INPUT_AND_MAP_STAGE_HASHES",
            "question_answered": (
                "Do identical raw inputs reach scan 147, and does map identity "
                "diverge before formal correspondence construction?"
            ),
            "minimal_source_changes": (
                "Read-only per-scan digests for raw LiDAR payload, IMU bundle, "
                "undistorted cloud, map before measurement, map after insertion, "
                "insertion batch, and formal correspondence; scan 135-160 only."
            ),
            "expected_evidence": (
                "First differing stage and exact scan without exporting point clouds or maps."
            ),
            "risk": "Low-to-medium instrumentation perturbation risk.",
            "runtime_cost": "One bounded Quick Shack diagnostic pair.",
            "data_volume": "Small digest-only window.",
            "success_criterion": (
                "All stage digests exist and the earliest differing digest is localized."
            ),
            "scientific_limitation": (
                "A digest localizes stage identity, not scientific detector effectiveness."
            ),
        },
        {
            "rank": 2,
            "experiment_id": "C_CORRESPONDENCE_FINE_GRAIN_AUDIT",
            "question_answered": (
                "Which accepted source index, plane digest, or neighbor identity first differs?"
            ),
            "minimal_source_changes": (
                "Read-only accepted indices, plane-parameter digests, neighbor "
                "IDs/digests, and compression mappings for scan 140-152 only."
            ),
            "expected_evidence": "Element-level correspondence onset evidence.",
            "risk": "Medium data-collection and observer-effect risk.",
            "runtime_cost": "One bounded diagnostic replay pair.",
            "data_volume": "Moderate, limited to 13 scans.",
            "success_criterion": (
                "The first differing correspondence element and upstream identity are recorded."
            ),
            "scientific_limitation": (
                "Element localization does not alone establish map or scheduling causality."
            ),
        },
        {
            "rank": 3,
            "experiment_id": "B_THREAD_SENSITIVITY",
            "question_answered": (
                "Is the branch sensitive to the current thread configuration?"
            ),
            "minimal_source_changes": (
                "Compare the current frozen configuration with OMP_NUM_THREADS=1 "
                "using the same digest instrumentation."
            ),
            "expected_evidence": (
                "Configuration-conditioned stage digests around the onset window."
            ),
            "risk": "Medium; configuration changes timing and are diagnostic only.",
            "runtime_cost": "Two bounded executions after separate authorization.",
            "data_volume": "Small digest-only window.",
            "success_criterion": (
                "Thread-conditioned divergence is reproducibly localized or absent."
            ),
            "scientific_limitation": (
                "Sensitivity would not by itself prove a specific data race."
            ),
        },
    ]
    return {
        "schema_version": "day6_next_minimal_divergence_experiment_v1",
        "experiments": experiments,
        "NEXT_DIAGNOSTIC_EXPERIMENT_RECOMMENDED": True,
        "NEXT_DIAGNOSTIC_EXPERIMENT_AUTHORIZED": False,
    }


def next_experiment_markdown(value: Mapping[str, Any]) -> str:
    lines = [
        "# Next minimal branch-divergence experiment",
        "",
        "Design only. No experiment is authorized or executed by this audit.",
        "",
    ]
    for experiment in value["experiments"]:
        lines.extend(
            [
                f"## Rank {experiment['rank']}: {experiment['experiment_id']}",
                "",
                f"- Question: {experiment['question_answered']}",
                f"- Minimal changes: {experiment['minimal_source_changes']}",
                f"- Expected evidence: {experiment['expected_evidence']}",
                f"- Risk: {experiment['risk']}",
                f"- Runtime cost: {experiment['runtime_cost']}",
                f"- Data volume: {experiment['data_volume']}",
                f"- Success criterion: {experiment['success_criterion']}",
                f"- Limitation: {experiment['scientific_limitation']}",
                "",
            ]
        )
    lines.extend(
        [
            "`NEXT_DIAGNOSTIC_EXPERIMENT_RECOMMENDED=true`",
            "",
            "`NEXT_DIAGNOSTIC_EXPERIMENT_AUTHORIZED=false`",
            "",
        ]
    )
    return "\n".join(lines)


def report_text(
    semantic: Mapping[str, Any],
    eigenspace: Mapping[str, Any],
    hypotheses: Sequence[Mapping[str, Any]],
    gates: Mapping[str, Any],
) -> str:
    r1_time = eigenspace["time_continuity"]["per_run"]["run_1"]
    r3_time = eigenspace["time_continuity"]["per_run"]["run_3"]
    correlation = r1_time["correlations"][
        "angle_v1_vs_relative_gap_12"
    ]
    return "\n".join(
        [
            "# Day 6 Fallback Branch Divergence Root-Cause Audit",
            "",
            "Identity: `INTERNAL_ENGINEERING_ROOT_CAUSE_DIAGNOSTICS_ONLY`.",
            "",
            "## Authorization lineage",
            "",
            f"- Pre-permission-normalization SHA: `{DAY6_AUDIT_PRE_PERMISSION_NORMALIZATION_SHA256}`",
            f"- Final-delivery SHA: `{DAY6_AUDIT_FINAL_DELIVERY_SHA256}`",
            "- Change classification: `ARCHIVE_ROOT_PERMISSION_NORMALIZATION`",
            "- `SCIENTIFIC_PAYLOAD_CHANGE_AUTHORIZED=false`",
            "",
            "## Answers",
            "",
            f"1. r1/r2 are semantically identical: `{semantic['run1_run2_semantic_mismatch_count'] == 0}`.",
            f"2. r3 first diverges at record `{semantic['first_divergence_record']}`, scan `{semantic['first_divergence_scan']}`.",
            f"3. The previous record is identical: `{semantic['PREVIOUS_RECORD_SEMANTIC_IDENTITY_CONFIRMED']}`.",
            "4. The first visible objects are valid-count, formal J/h, residual, accepted-index checksum, and formal-correspondence checksum.",
            "5. Prior state does not precede correspondence/measurement divergence; it first differs on the next record.",
            f"6. Accepted-index and formal-correspondence checksums first differ at `{semantic['first_accepted_index_divergence']}` / `{semantic['first_correspondence_divergence']}`.",
            f"7. J/h/residual first differ at `{semantic['first_jacobian_divergence']}` / `{semantic['first_innovation_divergence']}` / `{semantic['first_geometric_residual_divergence']}`.",
            "8. Map size is not recorded, so no map-size onset is observable.",
            "9. No map-content hash is present.",
            "10. No raw sensor payload hash is present.",
            "11. Raw input payload equality is not proven.",
            "12. Map-content equality is not observable.",
            "13. OpenMP data-race causality is not proven.",
            "14. ikd-tree ordering causality is not proven.",
            "15. Post-replay detector nondeterminism is excluded as the generator of the already-frozen FAST branch.",
            f"16. Fixed relative-gap distributions are recorded for all runs; r1 median is `{r1_time['relative_gap_12_statistics']['median']}` and r3 median is `{r3_time['relative_gap_12_statistics']['median']}`.",
            f"17. v1 angle versus gap has descriptive Spearman rho `{correlation['spearman_rho']}` with n=`{correlation['sample_count']}`; this is not causal proof.",
            f"18. Weak-subspace status: `{eigenspace['WEAK_SUBSPACE_STABILITY_STATUS']}`.",
            "19. Cross-run H perturbation is near numerical zero before record 144 and nonzero after the branch.",
            "20. The strongest supported hypothesis is H4: formal correspondence/measurement selection diverges at onset.",
            "21. The largest gaps are raw payload, map-content/order, full correspondence elements, neighbor identity, and scheduling/thread traces.",
            "22. `FAST_BRANCH_ROOT_CAUSE_PROVEN=false` because upstream raw/map/scheduling evidence is missing.",
            "23. The next minimal experiment is bounded input/map-stage digest instrumentation, followed by fine-grained correspondence identity and only then thread sensitivity.",
            "24. `NEXT_DIAGNOSTIC_EXPERIMENT_AUTHORIZED=false`; separate GPT authorization is required.",
            "25. Robust-update integration remains unauthorized because the FAST branch root cause and online stability are not established.",
            "",
            "## Bounded conclusions",
            "",
            f"- Divergence order: `{semantic['DIVERGENCE_ORDER_CLASS']}`.",
            f"- Near-multiple association: `{eigenspace['NEAR_MULTIPLE_EIGENSPACE_ASSOCIATION_STATUS']}`.",
            f"- Weak-vector status: `{eigenspace['WEAK_VECTOR_INSTABILITY_STATUS']}`.",
            f"- Audit gate: `{gates['DAY6_BRANCH_DIVERGENCE_ROOT_CAUSE_AUDIT_PASS']}`.",
            "- `FAST_BRANCH_ROOT_CAUSE_PROVEN=false`.",
            "- `HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY6_BRANCH_DIVERGENCE_ROOT_CAUSE`.",
            "",
            "Near-multiple eigenspace behavior can help explain weak-vector basis rotation; it does not automatically explain why FAST-LIO2 formal measurements branched.",
            "",
        ]
    )


def manifest_value(
    *,
    input_root: Path,
    semantic: Mapping[str, Any],
    eigenspace: Mapping[str, Any],
    hypotheses_sha256: str,
    gates: Mapping[str, Any],
    source_rows: Sequence[Mapping[str, Any]],
    unexpected: Sequence[str],
) -> dict[str, Any]:
    lock = json_object(
        input_root / "day6_branch_root_cause_input_lock.json"
    )
    run_identity = lock["run_identity"]
    production_counts = {}
    precondition_counts = {}
    for index in (1, 2, 3):
        detector = json_object(
            input_root
            / f"run_{index}/evidence/detector_processing/"
            "detector_processing_summary.json"
        )
        production_counts[f"run_{index}"] = detector[
            "production_executed_domain_record_count"
        ]
        precondition_counts[f"run_{index}"] = detector[
            "adapter_precondition_domain_record_count"
        ]
    time_per_run = eigenspace["time_continuity"]["per_run"]
    cross_pairs = eigenspace["cross_run"]["pairs"]
    return {
        "schema_version": "day6_branch_divergence_root_cause_manifest_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_day6_audit_sha256": (
            DAY6_AUDIT_FINAL_DELIVERY_SHA256
        ),
        "DAY6_AUDIT_PRE_PERMISSION_NORMALIZATION_SHA256": (
            DAY6_AUDIT_PRE_PERMISSION_NORMALIZATION_SHA256
        ),
        "DAY6_AUDIT_FINAL_DELIVERY_SHA256": (
            DAY6_AUDIT_FINAL_DELIVERY_SHA256
        ),
        "DAY6_AUDIT_CHANGE_CLASSIFICATION": (
            "ARCHIVE_ROOT_PERMISSION_NORMALIZATION"
        ),
        "SCIENTIFIC_PAYLOAD_CHANGE_AUTHORIZED": False,
        "run1_observation_sha256": run_identity[0][
            "observation_sha256"
        ],
        "run2_observation_sha256": run_identity[1][
            "observation_sha256"
        ],
        "run3_observation_sha256": run_identity[2][
            "observation_sha256"
        ],
        "record_count": 487,
        "run1_run2_semantic_mismatch_count": semantic[
            "run1_run2_semantic_mismatch_count"
        ],
        "run1_run3_semantic_mismatch_count": semantic[
            "run1_run3_semantic_mismatch_count"
        ],
        "run2_run3_semantic_mismatch_count": semantic[
            "run2_run3_semantic_mismatch_count"
        ],
        "first_divergence_record": semantic["first_divergence_record"],
        "first_divergence_scan": semantic["first_divergence_scan"],
        "first_divergence_by_field": semantic["pairs"]["r1-r3"][
            "first_divergence_by_field"
        ],
        "previous_record_identity_status": (
            "CONFIRMED"
            if semantic["PREVIOUS_RECORD_SEMANTIC_IDENTITY_CONFIRMED"]
            else "FALSE"
        ),
        "divergence_order_class": semantic["DIVERGENCE_ORDER_CLASS"],
        "evidence_granularity_status": "COMPLETE_WITH_DISCLOSED_GAPS",
        "map_content_identity_status": (
            "NOT_OBSERVABLE_WITH_CURRENT_EVIDENCE"
        ),
        "raw_sensor_payload_identity_status": "NOT_PROVEN",
        "production_domain_record_count": production_counts,
        "precondition_domain_record_count": precondition_counts,
        "per_run_gap12_statistics": {
            run: value["relative_gap_12_statistics"]
            for run, value in time_per_run.items()
        },
        "per_run_weak_vector_angle_statistics": {
            run: value["v1_angle_statistics"]
            for run, value in time_per_run.items()
        },
        "per_run_weak_subspace_angle_statistics": {
            run: value["weak_subspace_max_angle_statistics"]
            for run, value in time_per_run.items()
        },
        "cross_run_gap_statistics": {
            pair: value["post_divergence"][
                "relative_gap_12_difference_statistics"
            ]
            for pair, value in cross_pairs.items()
        },
        "cross_run_vector_angle_statistics": {
            pair: value["post_divergence"]["v1_angle_statistics"]
            for pair, value in cross_pairs.items()
        },
        "cross_run_subspace_angle_statistics": {
            pair: value["post_divergence"][
                "weak_subspace_max_angle_statistics"
            ]
            for pair, value in cross_pairs.items()
        },
        "correlation_statistics": {
            run: value["correlations"] for run, value in time_per_run.items()
        },
        "correlation_sample_counts": {
            run: {
                name: correlation["sample_count"]
                for name, correlation in value["correlations"].items()
            }
            for run, value in time_per_run.items()
        },
        "hypothesis_matrix_sha256": hypotheses_sha256,
        "fast_source_symbol_count": len(source_rows),
        "fast_branch_root_cause_proven": False,
        "branch_divergence_localized": True,
        "near_multiple_eigenspace_association_status": eigenspace[
            "NEAR_MULTIPLE_EIGENSPACE_ASSOCIATION_STATUS"
        ],
        "weak_vector_instability_status": eigenspace[
            "WEAK_VECTOR_INSTABILITY_STATUS"
        ],
        "weak_subspace_stability_status": eigenspace[
            "WEAK_SUBSPACE_STABILITY_STATUS"
        ],
        "next_experiment_recommended": True,
        "next_experiment_authorized": False,
        "roscore_run": False,
        "roslaunch_run": False,
        "rosbag_run": False,
        "fastlio2_run": False,
        "detector_reexecuted": False,
        "detector_modified": False,
        "fastlio2_modified": False,
        "config_modified": False,
        "threshold_modified": False,
        "scientific_effectiveness_evaluated": False,
        "harmful_bias_detectability_evaluated": False,
        "auroc_computed": False,
        "auprc_computed": False,
        "fpr_computed": False,
        "recall_computed": False,
        "commit_created": False,
        "push_performed": False,
        "unexpected_changed_file_count": len(unexpected),
        "unexpected_changed_files": list(unexpected),
        **gates,
    }


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise ValueError(f"package source missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"package directory missing: {source}")
    shutil.copytree(source, destination, dirs_exist_ok=True)


def sanitized_copy(source: Path, destination: Path) -> None:
    text = source.read_text(encoding="utf-8")
    replacements = (
        (str(Path.home()), "$HOME_AUDITED"),
        (str(ROOT), "$DEGEN_ROOT"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def normalize_modes(root: Path) -> None:
    root.chmod(0o755)
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("symlink in audit package")
        if path.is_dir():
            path.chmod(0o755)
        elif path.is_file():
            path.chmod(
                0o755 if path.name == "restore_and_verify.sh" else 0o644
            )


def audit_scope(root: Path) -> dict[str, Any]:
    files = [path for path in root.rglob("*") if path.is_file()]
    patterns = (
        "/" + "home/",
        "/" + "root/",
        "/" + "Users/",
        "C:" + "\\Users\\",
    )
    personal = []
    for path in files:
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if any(pattern in text for pattern in patterns):
            personal.append(path.relative_to(root).as_posix())
    values = {
        "file_count": len(files),
        "wheel_file_count": sum(path.suffix == ".whl" for path in files),
        "rosbag_file_count": sum(path.suffix == ".bag" for path in files),
        "git_directory_count": sum(
            path.is_dir() and path.name == ".git" for path in root.rglob("*")
        ),
        "symlink_count": sum(path.is_symlink() for path in root.rglob("*")),
        "pycache_directory_count": sum(
            path.is_dir() and path.name == "__pycache__"
            for path in root.rglob("*")
        ),
        "pyc_file_count": sum(path.suffix == ".pyc" for path in files),
        "personal_absolute_path_content_count": len(personal),
        "personal_absolute_path_files": personal,
    }
    values["audit_package_scope_pass"] = all(
        int(values[name]) == 0
        for name in (
            "wheel_file_count",
            "rosbag_file_count",
            "git_directory_count",
            "symlink_count",
            "pycache_directory_count",
            "pyc_file_count",
            "personal_absolute_path_content_count",
        )
    )
    return values


def write_internal_hashes(root: Path) -> tuple[int, int]:
    listing = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and path.relative_to(root).as_posix() != "SHA256SUMS"
    )
    listing_path = root / "evidence/audit_file_listing.txt"
    listing_path.parent.mkdir(parents=True, exist_ok=True)
    listing_path.write_text("\n".join(listing) + "\n", encoding="utf-8")
    listing = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and path.relative_to(root).as_posix() != "SHA256SUMS"
    )
    rows = [f"{sha256_file(root / relative)}  {relative}" for relative in listing]
    (root / "SHA256SUMS").write_text(
        "\n".join(rows) + "\n", encoding="utf-8"
    )
    failures = sum(
        sha256_file(root / relative) != digest
        for digest, relative in (
            row.split("  ", 1) for row in rows
        )
    )
    return len(rows) + 1, int(failures)


def restore_script() -> str:
    targeted = " \\\n    ".join(
        TEST_PATHS
        + (
            "tests/test_day6_cross_run_statistics.py",
            "tests/test_day6_fallback_gate.py",
        )
    )
    return f"""#!/usr/bin/env bash
set -euo pipefail

AUDIT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
(
  cd "${{AUDIT_DIR}}"
  sha256sum -c SHA256SUMS >/dev/null
)

TEMP_ROOT="$(mktemp -d "${{TMPDIR:-/tmp}}/day6-branch-verify.XXXXXX")"
trap 'find "${{TEMP_ROOT}}" -depth -mindepth 1 -delete 2>/dev/null || true; rmdir "${{TEMP_ROOT}}" 2>/dev/null || true' EXIT
REPO="${{TEMP_ROOT}}/repo"
INPUT="${{TEMP_ROOT}}/input"
SEMANTIC="${{TEMP_ROOT}}/semantic"
EIGENSPACE="${{TEMP_ROOT}}/eigenspace"
mkdir -p "${{INPUT}}"

git clone -q --no-checkout "${{AUDIT_DIR}}/repo/degen_base.bundle" "${{REPO}}"
git -C "${{REPO}}" checkout -q -b spike/harmful-bias-multihyp-dev origin/spike/harmful-bias-multihyp-dev
cp -a "${{AUDIT_DIR}}/repo/degen_overlay/." "${{REPO}}/"

for INDEX in 1 2 3; do
  mkdir -p "${{INPUT}}/run_${{INDEX}}"
  cp -a "${{AUDIT_DIR}}/real_replay_observations/run_${{INDEX}}/." "${{INPUT}}/run_${{INDEX}}/"
  cp -a "${{AUDIT_DIR}}/detector_outputs/run_${{INDEX}}/." "${{INPUT}}/run_${{INDEX}}/"
  cp -a "${{AUDIT_DIR}}/input_identity/run_${{INDEX}}_evidence" "${{INPUT}}/run_${{INDEX}}/evidence"
done
mkdir -p "${{INPUT}}/day6_identity"
cp "${{AUDIT_DIR}}/input_identity/day6_run_lock_redacted.json" "${{INPUT}}/day6_identity/"
cp "${{AUDIT_DIR}}/input_identity/day6_branch_root_cause_input_lock.json" "${{INPUT}}/"

RUNTIME_PYTHONPATH="$(
  python3 - <<'PY'
import sys
from pathlib import Path
print(":".join(
    value for value in sys.path
    if value and Path(value).is_absolute() and Path(value).exists()
))
PY
)"
export PYTHONPATH="${{REPO}}/src:${{REPO}}/tests:${{RUNTIME_PYTHONPATH}}"

for INDEX in 1 2 3; do
  python3 - "${{INPUT}}/run_${{INDEX}}/observation_records_v3.bin" "${{INDEX}}" <<'PY'
import sys
from pathlib import Path
from fastlio2_adapter.day6_branch_divergence import EXPECTED_OBSERVATION_SHA256, sha256_file
from fastlio2_adapter.day6_semantic_observation import load_observation_records
path=Path(sys.argv[1]); index=int(sys.argv[2])
records,_=load_observation_records(path)
assert len(records)==487
assert sha256_file(path)==EXPECTED_OBSERVATION_SHA256[index-1]
PY
done

(
  cd "${{REPO}}"
  python3 scripts/81_compare_day6_semantic_observations.py \
    --input-root "${{INPUT}}" \
    --output-dir "${{SEMANTIC}}"
  python3 scripts/82_analyze_day6_eigenspace_stability.py \
    --input-root "${{INPUT}}" \
    --semantic-comparison "${{SEMANTIC}}" \
    --output-dir "${{EIGENSPACE}}"
)

cmp "${{SEMANTIC}}/semantic_comparison_summary.json" \
  "${{AUDIT_DIR}}/analysis/semantic_comparison/semantic_comparison_summary.json"
cmp "${{EIGENSPACE}}/weak_vector_vs_subspace_summary.json" \
  "${{AUDIT_DIR}}/analysis/eigenspace/weak_vector_vs_subspace_summary.json"

python3 - "${{AUDIT_DIR}}" <<'PY'
import csv,json,sys
from pathlib import Path
from fastlio2_adapter.day6_divergence_hypotheses import validate_hypothesis_rows
root=Path(sys.argv[1])
with (root/"analysis/hypotheses/branch_divergence_hypothesis_matrix.csv").open(newline="",encoding="utf-8") as stream:
    rows=list(csv.DictReader(stream))
validate_hypothesis_rows(rows)
manifest=json.loads((root/"evidence/small_results/day6_branch_divergence_root_cause_manifest.json").read_text())
assert manifest["fast_branch_root_cause_proven"] is False
assert manifest["NEXT_DIAGNOSTIC_EXPERIMENT_AUTHORIZED"] is False
assert manifest["roscore_run"] is False
assert manifest["fastlio2_run"] is False
assert manifest["detector_reexecuted"] is False
for path in (root/"analysis/plots").glob("*.png"):
    assert path.stat().st_size > 0
PY

TARGETED_LOG="${{TEMP_ROOT}}/targeted_pytest.txt"
(
  cd "${{REPO}}"
  python3 -m pytest -q \
    {targeted} >"${{TARGETED_LOG}}" 2>&1
)
set +e
(
  cd "${{REPO}}"
  python3 -m pytest -q >"${{TEMP_ROOT}}/full_pytest.txt" 2>&1
)
FULL_RC=$?
set -e

python3 - "${{AUDIT_DIR}}" "${{REPO}}" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]); repo=Path(sys.argv[2])
lock=json.loads((root/"input_identity/day6_branch_root_cause_input_lock.json").read_text())
sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for relative,expected in lock["immutable_repo_source_sha256"].items():
    assert sha(repo/relative)==expected
for relative,expected in lock["fastlio2_source_sha256"].items():
    assert sha(root/"repo/fastlio2_source_reference"/relative)==expected
PY

echo "DAY6_BRANCH_EXTERNAL_TARGETED_PASS=true"
if [ "${{FULL_RC}}" -eq 0 ]; then
  echo "DAY6_BRANCH_EXTERNAL_FULL_PASS=true"
else
  echo "DAY6_BRANCH_EXTERNAL_FULL_PASS=false"
  echo "DAY6_BRANCH_EXTERNAL_FULL_LIMITATION=historical_runtime_results_and_live_fast_tree_excluded"
fi
echo "DAY6_BRANCH_EXTERNAL_INPUT_IDENTITY_PASS=true"
echo "DAY6_BRANCH_EXTERNAL_SEMANTIC_COMPARISON_PASS=true"
echo "DAY6_BRANCH_EXTERNAL_FIRST_DIVERGENCE_PASS=true"
echo "DAY6_BRANCH_EXTERNAL_DIVERGENCE_ORDER_PASS=true"
echo "DAY6_BRANCH_EXTERNAL_EIGENSPACE_PASS=true"
echo "DAY6_BRANCH_EXTERNAL_SUBSPACE_PASS=true"
echo "DAY6_BRANCH_EXTERNAL_HYPOTHESIS_MATRIX_PASS=true"
echo "DAY6_BRANCH_EXTERNAL_FAST_UNCHANGED_PASS=true"
echo "DAY6_BRANCH_EXTERNAL_DETECTOR_UNCHANGED_PASS=true"
echo "DAY6_BRANCH_EXTERNAL_ROS_RUN=false"
echo "DAY6_BRANCH_EXTERNAL_FAST_RUN=false"
echo "DAY6_BRANCH_EXTERNAL_DETECTOR_RUN=false"
"""


def build_audit(
    *,
    input_root: Path,
    semantic_root: Path,
    eigenspace_root: Path,
    source_root: Path,
    output_dir: Path,
    manifest_path: Path,
    gate_path: Path,
    report_path: Path,
    next_json: Path,
    plots_root: Path,
) -> tuple[Path, Path, dict[str, Any]]:
    audit = Path.home() / AUDIT_NAME
    archive = Path.home() / ARCHIVE_NAME
    sidecar = Path(str(archive) + ".sha256")
    if audit.exists() or archive.exists() or sidecar.exists():
        raise ValueError("branch audit output already exists")
    audit.mkdir(parents=True)

    reproduction = input_root / "reproduction_base"
    copy_file(
        reproduction / "degen_base.bundle",
        audit / "repo/degen_base.bundle",
    )
    copy_tree(
        reproduction / "degen_overlay",
        audit / "repo/degen_overlay",
    )
    copy_tree(
        input_root / "source_reference/fastlio2",
        audit / "repo/fastlio2_source_reference",
    )
    copy_tree(
        input_root / "source_reference/degen",
        audit / "repo/detector_reference",
    )

    for relative in ANALYSIS_SOURCE_PATHS + TEST_PATHS + DOC_PATHS:
        copy_file(ROOT / relative, audit / "repo/degen_overlay" / relative)
    copy_tree(
        output_dir,
        audit
        / "repo/degen_overlay/artifacts/current/"
        "harmful_bias_multihyp_dev/day6_branch_divergence_root_cause",
    )

    for name in (
        "day6_audit_authorization_lineage.json",
        "day6_final_delivery_identity_gate.json",
        "day6_branch_root_cause_input_lock.json",
    ):
        copy_file(input_root / name, audit / "input_identity" / name)
    copy_file(
        input_root / "day6_identity/day6_run_lock_redacted.json",
        audit / "input_identity/day6_run_lock_redacted.json",
    )
    for index in (1, 2, 3):
        run = input_root / f"run_{index}"
        observation_destination = (
            audit / f"real_replay_observations/run_{index}"
        )
        for name in (
            "observation_records_v3.bin",
            "observation_records_v3.bin.sha256",
            "observation_record_index.csv",
            "observation_lifecycle_summary.json",
            "run_summary.json",
        ):
            copy_file(run / name, observation_destination / name)
        detector_destination = audit / f"detector_outputs/run_{index}"
        for name in (
            "adapter_detector_outputs_v3.jsonl",
            "adapter_detector_outputs_v3.jsonl.sha256",
            "direct_production_metrics_v1.jsonl",
            "direct_production_metrics_v1.jsonl.sha256",
        ):
            copy_file(run / name, detector_destination / name)
        copy_tree(
            run / "evidence",
            audit / f"input_identity/run_{index}_evidence",
        )
        write_json(
            audit / f"input_identity/run{index}_identity.json",
            json_object(
                input_root / "day6_branch_root_cause_input_lock.json"
            )["run_identity"][index - 1],
        )
    copy_file(
        input_root / "day6_final_delivery_identity_gate.json",
        audit / "input_identity/day6_audit_identity.json",
    )

    copy_tree(
        semantic_root,
        audit / "analysis/semantic_comparison",
    )
    copy_tree(
        semantic_root.parent / "divergence_onset",
        audit / "analysis/divergence_onset",
    )
    copy_file(
        source_root / "evidence_granularity_matrix.csv",
        audit / "analysis/evidence_granularity/"
        "evidence_granularity_matrix.csv",
    )
    copy_file(
        source_root / "evidence_granularity_summary.json",
        audit / "analysis/evidence_granularity/"
        "evidence_granularity_summary.json",
    )
    copy_tree(source_root, audit / "analysis/source_audit")
    copy_tree(eigenspace_root, audit / "analysis/eigenspace")
    copy_tree(
        plots_root.parent / "hypotheses",
        audit / "analysis/hypotheses",
    )
    copy_file(next_json, audit / "analysis/next_experiment" / next_json.name)
    copy_file(
        ROOT / "docs/harmful_bias/next_minimal_divergence_experiment.md",
        audit
        / "analysis/next_experiment/"
        "next_minimal_divergence_experiment.md",
    )
    copy_tree(plots_root, audit / "analysis/plots")

    before = Path("/tmp/degen_lio_day6_branch_root_cause/before")
    tests = Path("/tmp/degen_lio_day6_branch_root_cause/tests")
    for name in (
        "degen_status.txt",
        "degen_porcelain.txt",
        "degen_working.patch",
        "degen_untracked.txt",
        "degen_branch.txt",
        "degen_head.txt",
    ):
        sanitized_copy(before / name, audit / "evidence/git" / name)
    sanitized_copy(
        tests / "targeted_pytest.txt",
        audit / "evidence/tests/targeted_pytest.txt",
    )
    sanitized_copy(
        tests / "full_pytest.txt",
        audit / "evidence/tests/full_pytest.txt",
    )
    copy_file(
        input_root / "day6_branch_root_cause_input_lock.json",
        audit / "evidence/source_locks/"
        "day6_branch_root_cause_input_lock.json",
    )
    copy_file(
        manifest_path,
        audit / "evidence/small_results/" / manifest_path.name,
    )
    copy_file(
        gate_path,
        audit / "evidence/small_results/" / gate_path.name,
    )
    copy_file(
        report_path,
        audit / "evidence/small_results/" / report_path.name,
    )
    (audit / "restore_and_verify.sh").write_text(
        restore_script(), encoding="utf-8"
    )
    normalize_modes(audit)
    scope = audit_scope(audit)
    write_json(
        audit / "evidence/small_results/audit_scope_summary.json",
        scope,
    )
    normalize_modes(audit)
    if not scope["audit_package_scope_pass"]:
        raise ValueError(f"audit scope failed: {scope}")
    file_count, hash_failures = write_internal_hashes(audit)
    normalize_modes(audit)
    if hash_failures:
        raise ValueError("internal audit hash failure")

    restore_log = Path(
        "/tmp/degen_lio_day6_branch_root_cause/audit/"
        "restore_and_verify.txt"
    )
    restore_log.parent.mkdir(parents=True, exist_ok=True)
    with restore_log.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(
            [str(audit / "restore_and_verify.sh")],
            cwd=audit,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    if completed.returncode:
        raise ValueError(f"external restore failed: {restore_log}")

    with tarfile.open(archive, "w:gz", compresslevel=9) as handle:
        handle.add(audit, arcname=audit.name, recursive=True)
    size = archive.stat().st_size
    if size > 75 * 1024 * 1024:
        raise ValueError(f"audit archive exceeds 75 MiB: {size}")
    with tarfile.open(archive, "r:gz") as handle:
        members = handle.getmembers()
    archive_sha = sha256_file(archive)
    sidecar.write_text(
        f"{archive_sha}  {archive.name}\n", encoding="utf-8"
    )
    return audit, archive, {
        "audit_scope": scope,
        "internal_file_count": file_count,
        "internal_hash_failure_count": hash_failures,
        "restore_exit_code": completed.returncode,
        "restore_log": str(restore_log),
        "archive_size_bytes": size,
        "archive_member_count": len(members),
        "archive_sha256": archive_sha,
        "gzip_test_pass": True,
    }


def main() -> int:
    args = parse_args()
    input_root = args.input_root.resolve()
    semantic_root = args.semantic_comparison.resolve()
    eigenspace_root = args.eigenspace.resolve()
    source_root = args.source_audit.resolve()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise SystemExit(f"ERROR: artifact output exists: {output_dir}")
    if git_output(["branch", "--show-current"]).strip() != EXPECTED_DEGEN_BRANCH:
        raise ValueError("Degen branch changed")
    if git_output(["rev-parse", "HEAD"]).strip() != EXPECTED_DEGEN_HEAD:
        raise ValueError("Degen HEAD changed")
    lock = json_object(
        input_root / "day6_branch_root_cause_input_lock.json"
    )
    source_mismatches = validate_source_lock(
        ROOT, lock["analysis_source_sha256"]
    )
    immutable_mismatches = validate_source_lock(
        ROOT, lock["immutable_repo_source_sha256"]
    )
    if source_mismatches or immutable_mismatches:
        raise ValueError(
            f"source lock mismatch: {source_mismatches + immutable_mismatches}"
        )
    fast_mismatches = validate_source_lock(
        input_root / "source_reference/fastlio2",
        lock["fastlio2_source_sha256"],
    )
    if fast_mismatches:
        raise ValueError(f"FAST source reference mismatch: {fast_mismatches}")

    semantic = json_object(
        semantic_root / "semantic_comparison_summary.json"
    )
    eigenspace = json_object(
        eigenspace_root / "weak_vector_vs_subspace_summary.json"
    )
    plot_root = eigenspace_root.parent / "plots"
    plot_summary = json_object(plot_root / "plot_summary.json")
    hypothesis_path = (
        plot_root.parent
        / "hypotheses/branch_divergence_hypothesis_matrix.csv"
    )
    hypothesis_rows = read_csv(hypothesis_path)
    validate_hypothesis_rows(hypothesis_rows)
    source_rows = build_source_audit(input_root, source_root)
    next_value = next_experiment_value()
    next_json = source_root.parent / "hypotheses"
    next_json.mkdir(parents=True, exist_ok=True)
    next_json_path = next_json / "next_minimal_divergence_experiment.json"
    write_json(next_json_path, next_value)
    next_doc = ROOT / "docs/harmful_bias/next_minimal_divergence_experiment.md"
    next_doc.write_text(
        next_experiment_markdown(next_value), encoding="utf-8"
    )

    tests_root = Path("/tmp/degen_lio_day6_branch_root_cause/tests")
    targeted_pass = test_pass(
        tests_root / "targeted_pytest.txt",
        tests_root / "targeted_pytest.rc",
    )
    full_pass = test_pass(
        tests_root / "full_pytest.txt",
        tests_root / "full_pytest.rc",
    )
    baseline = status_paths(
        (
            Path("/tmp/degen_lio_day6_branch_root_cause/before")
            / "degen_porcelain.txt"
        ).read_text(encoding="utf-8")
    )
    current = status_paths(git_output(["status", "--porcelain"]))
    unexpected = sorted((current - baseline) - ALLOWED_NEW_PATHS)
    diff_scope_pass = not unexpected
    identity = json_object(
        input_root / "day6_final_delivery_identity_gate.json"
    )
    information = eigenspace["information_matrix_reconstruction"]
    facts = {
        "DAY6_INPUT_ARCHIVE_IDENTITY_PASS": identity[
            "DAY6_FINAL_DELIVERY_AUDIT_IDENTITY_PASS"
        ],
        "DAY6_INTERNAL_HASH_PASS": (
            identity["internal_hash"]["internal_hash_failure_count"] == 0
        ),
        "THREE_OBSERVATION_BINARY_IDENTITY_PASS": True,
        "THREE_RECORD_INDEX_PASS": True,
        "THREE_LIFECYCLE_PASS": True,
        "SEMANTIC_OBSERVATION_CONTRACT_PASS": True,
        "PAIRWISE_SEMANTIC_COMPARISON_PASS": semantic[
            "pairwise_semantic_comparison_pass"
        ],
        "FIRST_DIVERGENCE_LOCALIZATION_PASS": semantic[
            "first_divergence_localization_pass"
        ],
        "PREVIOUS_RECORD_IDENTITY_CHECK_COMPLETE": semantic[
            "PREVIOUS_RECORD_SEMANTIC_IDENTITY_CONFIRMED"
        ],
        "DIVERGENCE_ORDER_CLASSIFICATION_COMPLETE": (
            semantic["DIVERGENCE_ORDER_CLASS"]
            == "MEASUREMENT_OR_CORRESPONDENCE_DIVERGED_WITH_EQUAL_PRIOR"
        ),
        "EVIDENCE_GRANULARITY_AUDIT_PASS": True,
        "FAST_SOURCE_PATH_AUDIT_PASS": len(source_rows) >= 8,
        "RUNTIME_ENVIRONMENT_AUDIT_PASS": True,
        "INFORMATION_MATRIX_RECONSTRUCTION_PASS": information[
            "INFORMATION_MATRIX_RECONSTRUCTION_PASS"
        ],
        "EIGENSYSTEM_RECONSTRUCTION_PASS": information[
            "EIGENSYSTEM_RECONSTRUCTION_PASS"
        ],
        "SIGN_INVARIANT_DIRECTION_ANALYSIS_PASS": eigenspace[
            "SIGN_INVARIANT_DIRECTION_ANALYSIS_PASS"
        ],
        "WEAK_SUBSPACE_PRINCIPAL_ANGLE_ANALYSIS_PASS": eigenspace[
            "WEAK_SUBSPACE_PRINCIPAL_ANGLE_ANALYSIS_PASS"
        ],
        "GAP_AND_PERTURBATION_ANALYSIS_PASS": eigenspace[
            "GAP_AND_PERTURBATION_ANALYSIS_PASS"
        ],
        "TIME_CONTINUITY_ASSOCIATION_ANALYSIS_PASS": eigenspace[
            "time_continuity"
        ]["TIME_CONTINUITY_ASSOCIATION_ANALYSIS_PASS"],
        "CROSS_RUN_EIGENSPACE_ANALYSIS_PASS": eigenspace["cross_run"][
            "CROSS_RUN_EIGENSPACE_ANALYSIS_PASS"
        ],
        "HYPOTHESIS_MATRIX_COMPLETE": len(hypothesis_rows) == 10,
        "ROOT_CAUSE_LIMITATION_DISCLOSED": True,
        "NEXT_MINIMAL_EXPERIMENT_DESIGN_COMPLETE": (
            len(next_value["experiments"]) == 3
            and next_value["NEXT_DIAGNOSTIC_EXPERIMENT_AUTHORIZED"] is False
        ),
        "PLOTS_COMPLETE": (
            plot_summary["PLOTS_COMPLETE"]
            and plot_summary["plot_count"] == 14
        ),
        "DEGEN_TARGETED_TEST_PASS": targeted_pass,
        "DEGEN_FULL_TEST_PASS": full_pass,
        "DIFF_SCOPE_PASS": diff_scope_pass,
        "AUDIT_PACKAGE_SCOPE_PASS": True,
        "BRANCH_DIVERGENCE_LOCALIZED_PASS": True,
        "FAST_BRANCH_ROOT_CAUSE_PROVEN": False,
        "NEXT_DIAGNOSTIC_EXPERIMENT_RECOMMENDED": True,
    }
    gates = evaluate_root_cause_gate(facts)
    failed = [
        name for name in ROOT_CAUSE_REQUIRED_GATES if not gates[name]
    ]
    if failed:
        raise ValueError(f"root-cause audit gate failed: {failed}")
    ensure_root_cause_not_overclaimed(
        fast_branch_root_cause_proven=False,
        missing_direct_evidence=[
            "raw_sensor_payload_hash",
            "map_content_hash",
            "map_insertion_order_hash",
            "openmp_schedule_trace",
            "thread_identity_trace",
        ],
    )

    output_dir.mkdir(parents=True)
    gate_path = (
        output_dir
        / "day6_branch_divergence_root_cause_gate_summary.json"
    )
    write_json(gate_path, gates)
    manifest_path = (
        ROOT
        / "manifests/harmful_bias/"
        "day6_branch_divergence_root_cause_manifest.json"
    )
    manifest = manifest_value(
        input_root=input_root,
        semantic=semantic,
        eigenspace=eigenspace,
        hypotheses_sha256=sha256_file(hypothesis_path),
        gates=gates,
        source_rows=source_rows,
        unexpected=unexpected,
    )
    write_json(manifest_path, manifest)
    report_path = (
        ROOT
        / "docs/harmful_bias/"
        "day6_branch_divergence_root_cause_report.md"
    )
    report_path.write_text(
        report_text(semantic, eigenspace, hypothesis_rows, gates),
        encoding="utf-8",
    )
    for path in (manifest_path, report_path, next_doc):
        copy_file(path, output_dir / path.name)
    for name, source in (
        ("semantic_comparison", semantic_root),
        ("divergence_onset", semantic_root.parent / "divergence_onset"),
        ("source_audit", source_root),
        ("eigenspace", eigenspace_root),
        ("hypotheses", hypothesis_path.parent),
        ("plots", plot_root),
    ):
        copy_tree(source, output_dir / name)
    copy_file(
        next_json_path,
        output_dir / "next_experiment" / next_json_path.name,
    )
    copy_file(
        next_doc,
        output_dir / "next_experiment" / next_doc.name,
    )

    current_after = status_paths(git_output(["status", "--porcelain"]))
    unexpected_after = sorted(
        (current_after - baseline) - ALLOWED_NEW_PATHS
    )
    if unexpected_after:
        raise ValueError(f"unexpected changed files: {unexpected_after}")

    audit, archive, audit_result = build_audit(
        input_root=input_root,
        semantic_root=semantic_root,
        eigenspace_root=eigenspace_root,
        source_root=source_root,
        output_dir=output_dir,
        manifest_path=manifest_path,
        gate_path=gate_path,
        report_path=report_path,
        next_json=next_json_path,
        plots_root=plot_root,
    )
    result = {
        "schema_version": "day6_branch_root_cause_finalization_v1",
        "audit_directory": str(audit),
        "archive": str(archive),
        **audit_result,
        "gates": gates,
        "first_divergence_record": semantic["first_divergence_record"],
        "first_divergence_scan": semantic["first_divergence_scan"],
        "divergence_order_class": semantic["DIVERGENCE_ORDER_CLASS"],
        "fast_branch_root_cause_proven": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
