#!/usr/bin/env python3
"""Render explicit no-data cards after the frozen PCL build-smoke stop."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


FIGURES = {
    "ideal_matched_backend_translation.png": (
        "IDEAL_MATCHED backend translation updates",
        "Phase A not run • intended 210 snapshots / 420 trials",
    ),
    "ideal_matched_backend_rotation.png": (
        "IDEAL_MATCHED backend rotation updates",
        "No q95 values exist; missing data is not a zero update",
    ),
    "ideal_matched_scene_breakdown.png": (
        "IDEAL_MATCHED scene breakdown",
        "All seven frozen scenes remained unexecuted",
    ),
    "open3d_vs_pcl_scene_ranking.png": (
        "Open3D vs PCL scene ranking",
        "Phase B not authorized because Phase A prerequisites were not met",
    ),
    "scene_signal_translation_error.png": (
        "Scene-signal translation error",
        "No INDEPENDENT_NOISE_FREE or FULL_NOISE trials were run",
    ),
}


def main() -> None:
    output = (
        ROOT
        / "artifacts/current/zero_perturbation_backend_qualification/figures"
    )
    output.mkdir(parents=True, exist_ok=True)
    for filename, (title, subtitle) in FIGURES.items():
        figure, axis = plt.subplots(figsize=(10, 5.8))
        figure.patch.set_facecolor("white")
        axis.set_facecolor("#F7F8FA")
        for spine in axis.spines.values():
            spine.set_color("#D9DEE5")
            spine.set_linewidth(1.0)
        axis.set_xticks([])
        axis.set_yticks([])
        axis.set_title(title, loc="left", fontsize=17, color="#232A31", pad=18)
        axis.text(
            0.0,
            1.015,
            subtitle,
            transform=axis.transAxes,
            fontsize=10.5,
            color="#5B6570",
            va="bottom",
        )
        axis.text(
            0.5,
            0.57,
            "NOT RUN",
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=28,
            fontweight="bold",
            color="#D87A2C",
        )
        axis.text(
            0.5,
            0.40,
            "PCL identical-cloud identity smoke failed\nbefore backend qualification.",
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=13,
            linespacing=1.5,
            color="#3568A8",
        )
        axis.text(
            0.5,
            0.19,
            "No parameter rescue • no Native trial • no Phase A / Phase B",
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=10.5,
            color="#5B6570",
        )
        figure.savefig(output / filename, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(figure)


if __name__ == "__main__":
    main()
