#!/usr/bin/env python3
"""Render standalone engineering-diagnostic plots for the branch audit."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.day6_branch_divergence import (  # noqa: E402
    write_json,
)
from fastlio2_adapter.day6_divergence_hypotheses import (  # noqa: E402
    build_hypothesis_rows,
)


PLOT_NAMES = (
    "first_divergence_field_timeline.png",
    "valid_correspondence_count_around_divergence.png",
    "prior_state_difference_around_divergence.png",
    "jacobian_difference_around_divergence.png",
    "information_matrix_perturbation_timeline.png",
    "relative_gap12_timeline_run1.png",
    "relative_gap12_timeline_run3.png",
    "weak_vector_angle_vs_gap12.png",
    "weak_vector_vs_subspace_angle_timeline.png",
    "cross_run_v1_angle_timeline.png",
    "cross_run_subspace_angle_timeline.png",
    "divergence_window_metric_comparison.png",
    "angle_distribution_by_gap_bin.png",
    "hypothesis_evidence_summary.png",
)
STATUS_SCORE = {
    "SUPPORTED": 4,
    "PARTIALLY_SUPPORTED": 3,
    "PLAUSIBLE_UNPROVEN": 2,
    "CONTRADICTED": 1,
    "NOT_OBSERVABLE": 0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--semantic-comparison",
        required=True,
        type=Path,
    )
    parser.add_argument("--eigenspace", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        raise ValueError("cannot write empty hypothesis matrix")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def finish(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def line_plot(
    path: Path,
    x: list[float],
    ys: list[tuple[str, list[float]]],
    *,
    title: str,
    xlabel: str,
    ylabel: str,
    vertical: Optional[float] = None,
) -> None:
    plt.figure(figsize=(8.4, 4.8))
    for label, values in ys:
        plt.plot(x, values, linewidth=1.1, label=label)
    if vertical is not None:
        plt.axvline(vertical, color="black", linestyle="--", linewidth=1)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    if len(ys) > 1:
        plt.legend()
    plt.grid(alpha=0.25)
    finish(path)


def main() -> int:
    args = parse_args()
    semantic = args.semantic_comparison.resolve()
    eigenspace = args.eigenspace.resolve()
    output = args.output_dir.resolve()
    if output.exists():
        raise SystemExit(f"ERROR: output already exists: {output}")
    output.mkdir(parents=True)
    divergence = semantic.parent / "divergence_onset"
    semantic_rows = read_csv(
        semantic / "semantic_observation_pairwise_comparison.csv"
    )
    comparison = json.loads(
        (semantic / "semantic_comparison_summary.json").read_text(
            encoding="utf-8"
        )
    )
    first = int(comparison["first_divergence_record"])
    window_rows = read_csv(divergence / "divergence_onset_window.csv")
    reconstruction = read_csv(
        eigenspace / "information_matrix_reconstruction.csv"
    )
    time_rows = read_csv(
        eigenspace / "weak_vector_vs_subspace_stability.csv"
    )
    cross_rows = read_csv(
        eigenspace / "cross_run_eigenspace_alignment.csv"
    )
    eig_summary = json.loads(
        (eigenspace / "weak_vector_vs_subspace_summary.json").read_text(
            encoding="utf-8"
        )
    )

    r13 = [row for row in semantic_rows if row["pair"] == "r1-r3"]
    field_names = (
        "prior_position_equal",
        "prior_covariance_equal",
        "valid_correspondence_count_equal",
        "jacobian_equal",
        "innovation_equal",
        "accepted_index_checksum_equal",
        "formal_correspondence_checksum_equal",
    )
    x = [int(row["record_index"]) for row in r13]
    difference_count = [
        sum(row[name] != "true" for name in field_names) for row in r13
    ]
    line_plot(
        output / PLOT_NAMES[0],
        x,
        [("differing field groups", difference_count)],
        title="Formal field divergence timeline: r1 versus r3",
        xlabel="record index",
        ylabel="differing field-group count",
        vertical=first,
    )

    window_by_run = {
        run: [row for row in window_rows if row["run"] == run]
        for run in ("run_1", "run_2", "run_3")
    }
    window_x = [
        int(row["record_index"]) for row in window_by_run["run_1"]
    ]
    line_plot(
        output / PLOT_NAMES[1],
        window_x,
        [
            (
                run,
                [
                    float(row["valid_correspondence_count"])
                    for row in window_by_run[run]
                ],
            )
            for run in ("run_1", "run_2", "run_3")
        ],
        title="Valid correspondence count around branch onset",
        xlabel="record index",
        ylabel="valid correspondence count",
        vertical=first,
    )

    prior_difference = []
    for left, right in zip(
        window_by_run["run_1"], window_by_run["run_3"]
    ):
        left_position = np.asarray(
            json.loads(left["prior_position_world"]), dtype=float
        )
        right_position = np.asarray(
            json.loads(right["prior_position_world"]), dtype=float
        )
        prior_difference.append(
            float(np.linalg.norm(right_position - left_position))
        )
    line_plot(
        output / PLOT_NAMES[2],
        window_x,
        [("position difference norm", prior_difference)],
        title="Prior-position difference around branch onset",
        xlabel="record index",
        ylabel="position difference norm",
        vertical=first,
    )

    jacobian_difference = [
        abs(
            int(right["jacobian_row_count"])
            - int(left["jacobian_row_count"])
        )
        for left, right in zip(
            window_by_run["run_1"], window_by_run["run_3"]
        )
    ]
    line_plot(
        output / PLOT_NAMES[3],
        window_x,
        [("Jacobian row-count difference", jacobian_difference)],
        title="Jacobian size difference around branch onset",
        xlabel="record index",
        ylabel="absolute row-count difference",
        vertical=first,
    )

    cross_r13 = [row for row in cross_rows if row["pair"] == "r1-r3"]
    cross_x = [int(row["record_index"]) for row in cross_r13]
    line_plot(
        output / PLOT_NAMES[4],
        cross_x,
        [
            (
                "relative H perturbation",
                [
                    float(row["relative_h_perturbation"])
                    for row in cross_r13
                ],
            )
        ],
        title="Cross-run information-matrix perturbation",
        xlabel="record index",
        ylabel="relative spectral perturbation",
        vertical=first,
    )

    reconstruction_by_run = {
        run: [row for row in reconstruction if row["run"] == run]
        for run in ("run_1", "run_3")
    }
    for run, plot_name in (
        ("run_1", PLOT_NAMES[5]),
        ("run_3", PLOT_NAMES[6]),
    ):
        rows = reconstruction_by_run[run]
        line_plot(
            output / plot_name,
            [int(row["record_index"]) for row in rows],
            [
                (
                    "relative gap 1-2",
                    [float(row["relative_gap_12"]) for row in rows],
                )
            ],
            title=f"Relative lambda1-lambda2 gap: {run}",
            xlabel="record index",
            ylabel="relative gap 1-2",
            vertical=first,
        )

    plt.figure(figsize=(8.4, 4.8))
    for run in ("run_1", "run_2", "run_3"):
        rows = [row for row in time_rows if row["run"] == run]
        plt.scatter(
            [float(row["relative_gap_12"]) for row in rows],
            [float(row["v1_sign_invariant_angle_deg"]) for row in rows],
            s=8,
            alpha=0.45,
            label=run,
        )
    plt.xscale("log")
    plt.title("Weak-vector angle versus relative gap 1-2")
    plt.xlabel("relative gap 1-2")
    plt.ylabel("sign-invariant v1 angle (degrees)")
    plt.legend()
    plt.grid(alpha=0.25)
    finish(output / PLOT_NAMES[7])

    time_run1 = [row for row in time_rows if row["run"] == "run_1"]
    line_plot(
        output / PLOT_NAMES[8],
        [int(row["record_index"]) for row in time_run1],
        [
            (
                "v1 angle",
                [
                    float(row["v1_sign_invariant_angle_deg"])
                    for row in time_run1
                ],
            ),
            (
                "2-D subspace max angle",
                [
                    float(row["subspace_angle_max_deg"])
                    for row in time_run1
                ],
            ),
        ],
        title="Adjacent weak-vector and subspace angles: run 1",
        xlabel="record index",
        ylabel="angle (degrees)",
        vertical=first,
    )

    line_plot(
        output / PLOT_NAMES[9],
        cross_x,
        [
            (
                "r1-r3 v1 angle",
                [
                    float(row["v1_sign_invariant_angle_deg"])
                    for row in cross_r13
                ],
            )
        ],
        title="Cross-run weak-vector angle timeline",
        xlabel="record index",
        ylabel="sign-invariant angle (degrees)",
        vertical=first,
    )
    line_plot(
        output / PLOT_NAMES[10],
        cross_x,
        [
            (
                "r1-r3 2-D subspace max angle",
                [
                    float(row["subspace_angle_max_deg"])
                    for row in cross_r13
                ],
            )
        ],
        title="Cross-run weak-subspace angle timeline",
        xlabel="record index",
        ylabel="max principal angle (degrees)",
        vertical=first,
    )

    line_plot(
        output / PLOT_NAMES[11],
        window_x,
        [
            (
                run,
                [float(row["odi_trans"]) for row in window_by_run[run]],
            )
            for run in ("run_1", "run_2", "run_3")
        ],
        title="Detector metric comparison in the branch window",
        xlabel="record index",
        ylabel="ODI (descriptive)",
        vertical=first,
    )

    labels = ["<1e-3", "1e-3..1e-2", "1e-2..1e-1", ">=1e-1"]
    bins = ["lt_1e-3", "1e-3_to_1e-2", "1e-2_to_1e-1", "ge_1e-1"]
    values = [
        [
            float(row["v1_sign_invariant_angle_deg"])
            for row in time_rows
            if row["gap_bin"] == name
        ]
        for name in bins
    ]
    plt.figure(figsize=(8.4, 4.8))
    nonempty_values = [value if value else [float("nan")] for value in values]
    plt.boxplot(nonempty_values, labels=labels, showfliers=False)
    plt.title("Adjacent weak-vector angles by fixed gap bin")
    plt.xlabel("relative gap 1-2 bin")
    plt.ylabel("sign-invariant v1 angle (degrees)")
    plt.grid(axis="y", alpha=0.25)
    finish(output / PLOT_NAMES[12])

    hypothesis_rows = build_hypothesis_rows(
        {
            "near_multiple_status": eig_summary[
                "NEAR_MULTIPLE_EIGENSPACE_ASSOCIATION_STATUS"
            ],
            "weak_subspace_status": eig_summary[
                "WEAK_SUBSPACE_STABILITY_STATUS"
            ],
        }
    )
    hypothesis_root = output.parent / "hypotheses"
    write_csv(
        hypothesis_root / "branch_divergence_hypothesis_matrix.csv",
        hypothesis_rows,
    )
    write_json(
        hypothesis_root / "branch_divergence_hypothesis_matrix.json",
        {
            "schema_version": "day6_branch_divergence_hypothesis_matrix_v1",
            "rows": hypothesis_rows,
            "probabilistic_confidence_used": False,
        },
    )
    plt.figure(figsize=(8.4, 4.8))
    positions = np.arange(len(hypothesis_rows))
    scores = [STATUS_SCORE[row["status"]] for row in hypothesis_rows]
    plt.bar(positions, scores, color="#4C78A8")
    plt.xticks(
        positions,
        [row["hypothesis_id"].split("_", 1)[0] for row in hypothesis_rows],
    )
    plt.yticks(
        range(5),
        [
            "not observable",
            "contradicted",
            "plausible",
            "partial",
            "supported",
        ],
    )
    plt.title("Bounded hypothesis evidence classification")
    plt.xlabel("hypothesis")
    plt.ylabel("evidence classification")
    plt.grid(axis="y", alpha=0.25)
    finish(output / PLOT_NAMES[13])

    missing = [name for name in PLOT_NAMES if not (output / name).is_file()]
    summary = {
        "schema_version": "day6_branch_root_cause_plot_summary_v1",
        "plot_count": len(PLOT_NAMES) - len(missing),
        "required_plot_count": len(PLOT_NAMES),
        "missing_plots": missing,
        "engineering_diagnostic_language_only": True,
        "PLOTS_COMPLETE": not missing,
    }
    write_json(output / "plot_summary.json", summary)
    if missing:
        raise ValueError(f"plots missing: {missing}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
