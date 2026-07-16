"""Four preregistered Matplotlib diagnostics for Stage 2 Day 12."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from eval.stage2_failure_day12_schema import DISCLOSURE_NOTE, padded_limits


FIGURE_NAMES = (
    "day12_fig01_innovation_timeline",
    "day12_fig02_prior_posterior_axis_error",
    "day12_fig03_same_sign_run_timeline",
    "day12_fig04_clean_stress_distributions",
)
SWEEPS = ("geometry", "observation")
METHODS = ("huber_full", "huber_projected_gain")
STRESSES = ("clean", "coherent_subhuber_slip")
METHOD_LABEL = {"huber_full": "Huber full", "huber_projected_gain": "Projected gain"}
STRESS_LABEL = {"clean": "Clean", "coherent_subhuber_slip": "Coherent"}


def generate_four_figures(
    figure_data: Mapping[str, Sequence[Mapping[str, Any]]], output_dir: Path, png_dpi: int = 300
) -> Sequence[Mapping[str, str]]:
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "figure.constrained_layout.use": True,
        "axes.grid": True, "grid.alpha": 0.2, "savefig.facecolor": "white",
    })
    target = Path(output_dir) / "figures"
    target.mkdir(parents=True, exist_ok=True)
    builders = (_figure1, _figure2, _figure3, _figure4)
    results = []
    for name, builder in zip(FIGURE_NAMES, builders):
        fig = builder(figure_data[name])
        bottom_margin = 0.075 if name.endswith("distributions") else 0.045
        layout_engine = fig.get_layout_engine()
        if layout_engine is not None:
            layout_engine.set(rect=(0.0, bottom_margin, 1.0, 1.0 - bottom_margin))
        fig.text(0.5, 0.004, DISCLOSURE_NOTE, ha="center", va="bottom", fontsize=8)
        png = target / f"{name}.png"
        pdf = target / f"{name}.pdf"
        fig.savefig(png, dpi=int(png_dpi), metadata={"Software": "Degen-LIO Day 12"})
        fig.savefig(pdf, metadata={"Creator": "Degen-LIO Day 12"})
        plt.close(fig)
        results.append({"figure_id": name, "png_path": str(png), "pdf_path": str(pdf)})
    return results


def _figure1(rows: Sequence[Mapping[str, Any]]):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True, sharey=True)
    values = []
    for row in rows:
        values.extend([float(row["weak_innovation_z_huber"]), float(row["huber_window_mean"])])
    limits = padded_limits(values)
    for row_index, sweep in enumerate(SWEEPS):
        for column, method in enumerate(METHODS):
            ax = axes[row_index, column]
            panel = [row for row in rows if row["sweep"] == sweep and row["method"] == method]
            _shade_active(ax, panel)
            styles = (
                ("clean", "weak_innovation_z_huber", "Clean frame", "#555555", "-", "o", 0.8),
                ("clean", "huber_window_mean", "Clean window", "#111111", "--", "s", 1.8),
                ("coherent_subhuber_slip", "weak_innovation_z_huber", "Coherent frame", "#888888", "-.", "^", 0.8),
                ("coherent_subhuber_slip", "huber_window_mean", "Coherent window", "#000000", ":", "D", 1.8),
            )
            for stress, field, label, color, line, marker, width in styles:
                selected = _select(panel, stress)
                ax.plot(_x(selected), _y(selected, field), label=label, color=color,
                        linestyle=line, marker=marker, markersize=2.8, markevery=4, linewidth=width)
            ax.axhline(0.0, color="black", linewidth=0.7, alpha=0.65)
            ax.set_ylim(*limits)
            ax.set_title(f"{sweep.title()} — {METHOD_LABEL[method]}")
            ax.set_xlabel("Frame index")
            if column == 0:
                ax.set_ylabel("Weak-direction standardized innovation score")
            if row_index == 0 and column == 0:
                ax.legend(fontsize=7, ncol=2, loc="best")
    fig.suptitle("Innovation and frozen-window timelines")
    return fig


def _figure2(rows: Sequence[Mapping[str, Any]]):
    fig, axes = plt.subplots(2, 4, figsize=(16, 8), sharex=True, sharey=True)
    values = [float(row[field]) for row in rows for field in (
        "prior_axis_error_abs_m", "posterior_axis_error_abs_m"
    )]
    limits = padded_limits(values)
    columns = tuple((stress, method) for stress in STRESSES for method in METHODS)
    for row_index, sweep in enumerate(SWEEPS):
        for column, (stress, method) in enumerate(columns):
            ax = axes[row_index, column]
            panel = [row for row in rows if row["sweep"] == sweep and row["method"] == method and row["stress"] == stress]
            _shade_active(ax, panel)
            ax.plot(_x(panel), _y(panel, "prior_axis_error_abs_m"), color="#666666",
                    linestyle="--", marker="o", markevery=4, markersize=3, label="Prior", linewidth=1.2)
            ax.plot(_x(panel), _y(panel, "posterior_axis_error_abs_m"), color="#000000",
                    linestyle="-", marker="s", markevery=4, markersize=3, label="Posterior", linewidth=1.5)
            ax.set_ylim(*limits)
            ax.set_title(f"{STRESS_LABEL[stress]} / {METHOD_LABEL[method]}")
            ax.set_xlabel("Frame index")
            if column == 0:
                ax.set_ylabel(f"{sweep.title()}\nAbsolute axial error (m)")
            if row_index == 0 and column == 0:
                ax.legend(fontsize=8)
    fig.suptitle("Prior and posterior absolute axial error")
    return fig


def _figure3(rows: Sequence[Mapping[str, Any]]):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True, sharey=True)
    limits = padded_limits([float(row["huber_current_same_sign_run_length"]) for row in rows], integer=True)
    for row_index, sweep in enumerate(SWEEPS):
        for column, method in enumerate(METHODS):
            ax = axes[row_index, column]
            panel = [row for row in rows if row["sweep"] == sweep and row["method"] == method]
            _shade_active(ax, panel)
            for stress, color, line, marker in (
                ("clean", "#555555", "--", "o"),
                ("coherent_subhuber_slip", "#000000", "-", "s"),
            ):
                selected = _select(panel, stress)
                ax.step(_x(selected), _y(selected, "huber_current_same_sign_run_length"),
                        where="post", color=color, linestyle=line, marker=marker,
                        markevery=4, markersize=3, label=STRESS_LABEL[stress])
            ax.set_ylim(*limits)
            ax.set_title(f"{sweep.title()} — {METHOD_LABEL[method]}")
            ax.set_xlabel("Frame index")
            if column == 0:
                ax.set_ylabel("Current same-sign run length (frames)")
            if row_index == 0 and column == 0:
                ax.legend(fontsize=8)
    fig.suptitle("Current same-sign run timelines")
    return fig


def _figure4(rows: Sequence[Mapping[str, Any]]):
    fig, axes = plt.subplots(4, 2, figsize=(12, 14), sharex=True)
    metrics = (
        ("abs_weak_innovation_z_huber", "Absolute innovation score"),
        ("abs_huber_window_mean", "Absolute window mean"),
        ("abs_huber_cusum_signed", "Absolute signed CUSUM"),
        ("huber_current_same_sign_run_length", "Current same-sign run (frames)"),
    )
    groups = tuple((method, stress) for method in METHODS for stress in STRESSES)
    for metric_index, (metric, label) in enumerate(metrics):
        metric_values = [float(row["metric_value"]) for row in rows if row["metric_name"] == metric and _as_bool(row["included"])]
        limits = padded_limits(metric_values, integer=metric.endswith("run_length"))
        for column, sweep in enumerate(SWEEPS):
            ax = axes[metric_index, column]
            grouped = []
            for method, stress in groups:
                grouped.append([
                    float(row["metric_value"]) for row in rows
                    if row["metric_name"] == metric and row["sweep"] == sweep
                    and row["method"] == method and row["stress"] == stress and _as_bool(row["included"])
                ])
            ax.boxplot(grouped, positions=np.arange(1, 5), widths=0.5, showfliers=False,
                       medianprops={"color": "black", "linewidth": 1.4},
                       boxprops={"color": "#444444"}, whiskerprops={"color": "#444444"},
                       capprops={"color": "#444444"})
            for position, (method, stress) in enumerate(groups, start=1):
                selected = [row for row in rows if row["metric_name"] == metric and row["sweep"] == sweep
                            and row["method"] == method and row["stress"] == stress and _as_bool(row["included"])]
                x_values = [position + float(row["deterministic_jitter"]) for row in selected]
                y_values = [float(row["metric_value"]) for row in selected]
                marker = "o" if stress == "clean" else "s"
                face = "none" if method == "huber_full" else "#555555"
                ax.scatter(x_values, y_values, s=14, marker=marker, facecolors=face,
                           edgecolors="black", linewidths=0.5, alpha=0.75)
            ax.set_ylim(*limits)
            ax.set_title(sweep.title())
            ax.set_ylabel(label)
            ax.set_xticks(np.arange(1, 5))
            ax.set_xticklabels(("Full\nClean", "Full\nCoherent", "Projected\nClean", "Projected\nCoherent"), fontsize=7)
    fig.suptitle("Clean/coherent frame-wise descriptive distributions")
    fig.text(0.5, 0.022, "Frame-wise values are serially correlated; boxes are descriptive only.",
             ha="center", fontsize=9)
    return fig


def _shade_active(ax, rows: Sequence[Mapping[str, Any]]) -> None:
    active = sorted({int(row["frame_index"]) for row in rows if row["stress"] == "coherent_subhuber_slip" and _as_bool(row["stress_active"])})
    if not active:
        return
    starts = [active[0]]
    ends = []
    for first, second in zip(active, active[1:]):
        if second != first + 1:
            ends.append(first)
            starts.append(second)
    ends.append(active[-1])
    for start, end in zip(starts, ends):
        ax.axvspan(start - 0.5, end + 0.5, color="#dddddd", alpha=0.35, zorder=0)


def _select(rows: Sequence[Mapping[str, Any]], stress: str) -> list[Mapping[str, Any]]:
    return sorted((row for row in rows if row["stress"] == stress), key=lambda row: int(row["frame_index"]))


def _x(rows: Sequence[Mapping[str, Any]]) -> list[int]:
    return [int(row["frame_index"]) for row in rows]


def _y(rows: Sequence[Mapping[str, Any]], field: str) -> list[float]:
    return [float(row[field]) for row in rows]


def _as_bool(value: Any) -> bool:
    return value is True or str(value) == "True"
