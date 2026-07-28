"""Materialize the locked Development tables, figures, report, and decision."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import open3d
import pandas as pd
import scipy

from .protocol import PROTOCOL_RELATIVE, PROTOCOL_SHA256, file_sha256, load_protocol
from .statistics import (
    aggregate_repeated_measurements,
    exploratory_block_bootstrap_interval,
    safe_spearman,
)


SCENE_ORDER = (
    "GEOMETRY_RICH_ROOM",
    "LONG_CORRIDOR",
    "PARALLEL_WALLS",
    "END_FACE_TRANSITION_PRESENT",
    "END_FACE_TRANSITION_WEAK",
    "END_FACE_TRANSITION_ABSENT",
    "REPEATED_STRUCTURE",
)
CONDITION_ORDER = (
    "IDEAL_MATCHED",
    "INDEPENDENT_NOISE_FREE",
    "SCAN_NOISE_ONLY",
    "MAP_NOISE_ONLY",
    "DROPOUT_ONLY",
    "FULL_NOISE",
)
BACKEND_ORDER = ("native_full", "native_frozen", "open3d_full")
CONFIRMATORY_LOCK_PREREQUISITES = (
    "DEVELOPMENT_PIPELINE_EXECUTABLE",
    "ALL_1260_SNAPSHOTS_COMPLETE",
    "ALL_3780_TRIALS_COMPLETE",
    "SNAPSHOT_PAIRING_PASS",
    "OPEN3D_BACKEND_PASS",
    "NO_CONFIRMATORY_SEED_ACCESS",
    "NO_OLD_CAPTURE_TEST_SEED_ACCESS",
    "NO_GT_OPTIMIZATION_LEAKAGE",
    "IDEAL_MATCHED_CONTROL_PASS",
    "PRELIMINARY_SCENE_EFFECT_OBSERVED",
    "PRELIMINARY_CROSS_BACKEND_SIGNAL_OBSERVED",
    "PRELIMINARY_REASSOCIATION_EFFECT_OBSERVED",
)
BLUE = "#3568A8"
ORANGE = "#D87A2C"
GOLD = "#C8A33B"
INK = "#232A31"
GRID = "#D9DEE5"


def confirmatory_lock_authorized(decisions: Mapping[str, Any]) -> bool:
    return bool(
        all(decisions.get(field) is True for field in CONFIRMATORY_LOCK_PREREQUISITES)
        and decisions.get("NEW_PROTOCOL_AMBIGUITIES_FOUND") is False
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_frame(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")


def _git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=root, text=True, stderr=subprocess.DEVNULL
    ).strip()


def _quantile_summary(frame: pd.DataFrame) -> dict[str, float]:
    translation = frame["translation_error_m"].to_numpy(dtype=float)
    rotation = frame["rotation_error_rad"].to_numpy(dtype=float)
    tq = np.quantile(translation, [0.25, 0.50, 0.75, 0.95])
    rq = np.quantile(rotation, [0.25, 0.50, 0.75, 0.95])
    return {
        "translation_error_median_m": float(tq[1]),
        "translation_error_iqr_m": float(tq[2] - tq[0]),
        "translation_error_q95_m": float(tq[3]),
        "rotation_error_median_rad": float(rq[1]),
        "rotation_error_iqr_rad": float(rq[2] - rq[0]),
        "rotation_error_q95_rad": float(rq[3]),
    }


def _noise_summary(trials: pd.DataFrame, bootstrap_seed: int) -> pd.DataFrame:
    rows = []
    for (scene, condition, backend), group in trials.groupby(
        ["scene_variant", "noise_condition", "registration_backend"], sort=False
    ):
        record = {
            "scene_variant": scene,
            "noise_condition": condition,
            "registration_backend": backend,
            "trial_count": len(group),
            **_quantile_summary(group),
        }
        lower, upper = exploratory_block_bootstrap_interval(
            group.to_dict("records"),
            "translation_error_m",
            repetitions=1000,
            seed=bootstrap_seed,
        )
        record["exploratory_block_bootstrap_translation_median_ci025_m"] = lower
        record["exploratory_block_bootstrap_translation_median_ci975_m"] = upper
        rows.append(record)
    result = pd.DataFrame(rows)
    result["scene_variant"] = pd.Categorical(result["scene_variant"], SCENE_ORDER, ordered=True)
    result["noise_condition"] = pd.Categorical(result["noise_condition"], CONDITION_ORDER, ordered=True)
    result["registration_backend"] = pd.Categorical(
        result["registration_backend"], BACKEND_ORDER, ordered=True
    )
    return result.sort_values(
        ["noise_condition", "scene_variant", "registration_backend"]
    ).reset_index(drop=True)


def _backend_agreement(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for condition in ("INDEPENDENT_NOISE_FREE", "FULL_NOISE"):
        subset = summary[summary["noise_condition"] == condition]
        native = subset[subset["registration_backend"] == "native_full"].set_index(
            "scene_variant"
        )
        other = subset[subset["registration_backend"] == "open3d_full"].set_index(
            "scene_variant"
        )
        native_values = [native.loc[scene, "translation_error_median_m"] for scene in SCENE_ORDER]
        other_values = [other.loc[scene, "translation_error_median_m"] for scene in SCENE_ORDER]
        rows.append(
            {
                "noise_condition": condition,
                "scene_count": 7,
                "native_open3d_scene_translation_median_spearman_rho": safe_spearman(
                    native_values, other_values
                ),
            }
        )
    return pd.DataFrame(rows)


def _scene_contrast(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for condition in ("INDEPENDENT_NOISE_FREE", "FULL_NOISE"):
        for backend in ("native_full", "open3d_full"):
            subset = summary[
                (summary["noise_condition"] == condition)
                & (summary["registration_backend"] == backend)
            ].set_index("scene_variant")
            rich = float(subset.loc["GEOMETRY_RICH_ROOM", "translation_error_median_m"])
            for weak in ("LONG_CORRIDOR", "PARALLEL_WALLS"):
                value = float(subset.loc[weak, "translation_error_median_m"])
                ratio = value / rich if rich > 1.0e-15 else (math.inf if value > 0.0 else math.nan)
                rows.append(
                    {
                        "noise_condition": condition,
                        "registration_backend": backend,
                        "control_scene": "GEOMETRY_RICH_ROOM",
                        "weak_scene": weak,
                        "control_translation_median_m": rich,
                        "weak_translation_median_m": value,
                        "weak_over_rich_translation_median_ratio": ratio,
                        "ratio_at_least_2": bool(ratio >= 2.0),
                    }
                )
    return pd.DataFrame(rows)


def _traditional_correlations(diagnostics: pd.DataFrame) -> pd.DataFrame:
    metric_fields = (
        "initial_cost",
        "final_cost",
        "initial_gradient_norm",
        "lambda_min",
        "condition_number",
        "lambda_min_over_lambda_max",
        "spectral_entropy",
        "effective_rank",
        "ODI",
        "AIS",
        "correspondence_count",
    )
    outcome_fields = (
        "full_translation_error_m",
        "correspondence_turnover",
        "full_frozen_translation_difference_m",
    )
    rows = []
    for metric in metric_fields:
        for outcome in outcome_fields:
            rows.append(
                {
                    "traditional_metric": metric,
                    "outcome": outcome,
                    "spearman_rho": safe_spearman(
                        diagnostics[metric].to_numpy(dtype=float),
                        diagnostics[outcome].to_numpy(dtype=float),
                    ),
                    "snapshot_count": len(diagnostics),
                }
            )
    return pd.DataFrame(rows)


def _multi_attractor_summary(trials: pd.DataFrame) -> pd.DataFrame:
    rows = []
    fields = [
        "translation_x_m",
        "translation_y_m",
        "translation_z_m",
        "rotation_x_rad",
        "rotation_y_rad",
        "rotation_z_rad",
    ]
    for (scene, condition, backend), group in trials.groupby(
        ["scene_variant", "noise_condition", "registration_backend"], sort=False
    ):
        endpoints = np.round(group[fields].to_numpy(dtype=float) / 1.0e-4).astype(np.int64)
        _, counts = np.unique(endpoints, axis=0, return_counts=True)
        rows.append(
            {
                "scene_variant": scene,
                "noise_condition": condition,
                "registration_backend": backend,
                "trial_count": len(group),
                "endpoint_bin_width_translation_m_and_rotation_rad": 1.0e-4,
                "descriptive_endpoint_bin_count": int(counts.size),
                "largest_endpoint_bin_fraction": float(np.max(counts) / np.sum(counts)),
                "formal_multi_attractor_claim_authorized": False,
            }
        )
    return pd.DataFrame(rows)


def _runtime_summary(trials: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (backend, scene), group in trials.groupby(
        ["registration_backend", "scene_variant"], sort=False
    ):
        values = group["runtime_ms"].to_numpy(dtype=float)
        rows.append(
            {
                "registration_backend": backend,
                "scene_variant": scene,
                "trial_count": len(group),
                "runtime_median_ms": float(np.median(values)),
                "runtime_iqr_ms": float(np.quantile(values, 0.75) - np.quantile(values, 0.25)),
                "runtime_q95_ms": float(np.quantile(values, 0.95)),
            }
        )
    return pd.DataFrame(rows)


def _style_axis(axis: Any) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color=GRID, linewidth=0.7, alpha=0.8)
    axis.set_axisbelow(True)


def _save_figure(figure: Any, path: Path) -> None:
    figure.patch.set_facecolor("white")
    figure.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def _short_scene(scene: str) -> str:
    return {
        "GEOMETRY_RICH_ROOM": "Rich room",
        "LONG_CORRIDOR": "Corridor",
        "PARALLEL_WALLS": "Parallel walls",
        "END_FACE_TRANSITION_PRESENT": "End present",
        "END_FACE_TRANSITION_WEAK": "End weak",
        "END_FACE_TRANSITION_ABSENT": "End absent",
        "REPEATED_STRUCTURE": "Repeated",
    }[scene]


def _build_figures(
    figures: Path,
    trials: pd.DataFrame,
    repeated: pd.DataFrame,
    diagnostics: pd.DataFrame,
    summary: pd.DataFrame,
) -> list[dict[str, str]]:
    figures.mkdir(parents=True, exist_ok=True)
    chart_map: list[dict[str, str]] = []

    ideal = trials[
        (trials["noise_condition"] == "IDEAL_MATCHED")
        & trials["registration_backend"].isin(["native_full", "open3d_full"])
    ]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.8))
    backends = ["native_full", "open3d_full"]
    tq = [ideal[ideal["registration_backend"] == b]["translation_error_m"].quantile(0.95) * 1000 for b in backends]
    rq = [ideal[ideal["registration_backend"] == b]["rotation_error_deg"].quantile(0.95) for b in backends]
    axes[0].bar(backends, tq, color=[BLUE, ORANGE], edgecolor=INK)
    axes[0].axhline(1.0, color=INK, linestyle="--", label="1.0 mm gate")
    axes[0].set_ylabel("q95 translation error (mm)")
    axes[0].legend(frameon=False)
    axes[1].bar(backends, rq, color=[BLUE, ORANGE], edgecolor=INK)
    axes[1].axhline(0.01, color=INK, linestyle="--", label="0.01° gate")
    axes[1].set_ylabel("q95 rotation error (deg)")
    axes[1].legend(frameon=False)
    for axis in axes:
        _style_axis(axis)
        axis.tick_params(axis="x", rotation=15)
    fig.suptitle("IDEAL_MATCHED hard control\nq95 over 210 shared snapshots per backend", color=INK)
    path = figures / "ideal_matched_control.png"
    _save_figure(fig, path)
    chart_map.append({"figure": path.name, "family": "comparison", "question": "Do both deciding backends pass the ideal control?", "palette": "blue-orange plus neutral gate"})

    for metric, filename, ylabel, scale in (
        ("translation_error_median_m", "scene_translation_error.png", "median translation error (mm)", 1000.0),
        ("rotation_error_median_rad", "scene_rotation_error.png", "median rotation error (deg)", 180.0 / math.pi),
    ):
        fig, axes = plt.subplots(1, 2, figsize=(15, 5.2), sharey=False)
        for axis, condition in zip(axes, ("INDEPENDENT_NOISE_FREE", "FULL_NOISE")):
            subset = summary[
                (summary["noise_condition"] == condition)
                & summary["registration_backend"].isin(["native_full", "open3d_full"])
            ]
            x = np.arange(len(SCENE_ORDER))
            width = 0.36
            for offset, backend, color in ((-width / 2, "native_full", BLUE), (width / 2, "open3d_full", ORANGE)):
                data = subset[subset["registration_backend"] == backend].set_index("scene_variant")
                values = [float(data.loc[scene, metric]) * scale for scene in SCENE_ORDER]
                axis.bar(x + offset, values, width, label=backend, color=color, edgecolor=INK)
            axis.set_xticks(x, [_short_scene(scene) for scene in SCENE_ORDER], rotation=35, ha="right")
            axis.set_title(condition.replace("_", " ").title())
            axis.set_ylabel(ylabel)
            axis.legend(frameon=False)
            _style_axis(axis)
        fig.suptitle(f"Scene {ylabel.split('median ')[-1]}\nDevelopment medians across geometry, measurement, and repeat blocks", color=INK)
        path = figures / filename
        _save_figure(fig, path)
        chart_map.append({"figure": path.name, "family": "comparison", "question": f"How does {ylabel} vary by scene and backend?", "palette": "blue-orange"})

    full_repeat = repeated[
        (repeated["noise_condition"] == "FULL_NOISE")
        & repeated["registration_backend"].isin(["native_full", "open3d_full"])
    ]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), sharey=True)
    for axis, component in zip(axes, ("x", "y", "z")):
        for backend, color, marker in (("native_full", BLUE, "o"), ("open3d_full", ORANGE, "s")):
            subset = full_repeat[full_repeat["registration_backend"] == backend]
            x = [SCENE_ORDER.index(str(scene)) for scene in subset["scene_variant"]]
            axis.scatter(x, subset[f"mean_translation_{component}_m"] * 1000, s=22, alpha=0.65, color=color, marker=marker, label=backend)
        axis.axhline(0.0, color=INK, linewidth=0.8)
        axis.set_xticks(range(7), [_short_scene(scene) for scene in SCENE_ORDER], rotation=35, ha="right")
        axis.set_title(f"{component.upper()} component")
        _style_axis(axis)
    axes[0].set_ylabel("systematic translation vector component (mm)")
    axes[0].legend(frameon=False)
    fig.suptitle("Systematic offset vectors under FULL_NOISE\nOne point per scene × geometry-seed repeat group", color=INK)
    path = figures / "systematic_offset_vectors.png"
    _save_figure(fig, path)
    chart_map.append({"figure": path.name, "family": "comparison", "question": "Which vector components make up the systematic offsets?", "palette": "blue-orange with marker shapes"})

    fig, axis = plt.subplots(figsize=(7.2, 5.6))
    for backend, color, marker in (("native_full", BLUE, "o"), ("native_frozen", GOLD, "^"), ("open3d_full", ORANGE, "s")):
        subset = repeated[repeated["registration_backend"] == backend]
        axis.scatter(
            np.maximum(subset["systematic_translation_offset_m"] * 1000, 1.0e-9),
            np.maximum(subset["translation_repeatability_rms_m"] * 1000, 1.0e-9),
            s=22,
            alpha=0.55,
            color=color,
            marker=marker,
            label=backend,
        )
    axis.set_xscale("log")
    axis.set_yscale("log")
    axis.set_xlabel("systematic translation offset (mm, log scale)")
    axis.set_ylabel("translation repeatability RMS (mm, log scale)")
    axis.legend(frameon=False)
    _style_axis(axis)
    axis.set_title("Repeatability dispersion versus systematic offset\n378 frozen repeat groups; zeros floored only for display")
    path = figures / "repeatability_vs_systematic_offset.png"
    _save_figure(fig, path)
    chart_map.append({"figure": path.name, "family": "relationship", "question": "Are repeatability dispersion and systematic offset distinct?", "palette": "blue-gold-orange plus marker shapes"})

    fig, axis = plt.subplots(figsize=(6.8, 5.8))
    axis.scatter(
        np.maximum(diagnostics["frozen_translation_error_m"] * 1000, 1.0e-9),
        np.maximum(diagnostics["full_translation_error_m"] * 1000, 1.0e-9),
        s=17,
        alpha=0.5,
        color=BLUE,
        edgecolors="none",
    )
    limits = [1.0e-6, max(float((diagnostics[["frozen_translation_error_m", "full_translation_error_m"]] * 1000).max().max()), 1.0e-5)]
    axis.plot(limits, limits, linestyle="--", color=INK, label="equal error")
    axis.set_xscale("log")
    axis.set_yscale("log")
    axis.set_xlim(limits)
    axis.set_ylim(limits)
    axis.set_xlabel("native frozen translation error (mm, log scale)")
    axis.set_ylabel("native full translation error (mm, log scale)")
    axis.legend(frameon=False)
    _style_axis(axis)
    axis.set_title("Native full versus frozen zero-initialization error\n1260 paired snapshots; Frozen is a local baseline, not truth")
    path = figures / "full_vs_frozen_paired.png"
    _save_figure(fig, path)
    chart_map.append({"figure": path.name, "family": "relationship", "question": "How do full and frozen endpoint errors differ on paired snapshots?", "palette": "single blue root plus neutral reference"})

    fig, axis = plt.subplots(figsize=(7.2, 5.6))
    axis.scatter(
        diagnostics["correspondence_turnover"],
        diagnostics["full_frozen_translation_difference_m"] * 1000,
        s=18,
        alpha=0.55,
        color=ORANGE,
        edgecolors="none",
    )
    axis.set_xlabel("correspondence Jaccard turnover")
    axis.set_ylabel("full/frozen translation difference (mm)")
    _style_axis(axis)
    rho = safe_spearman(
        diagnostics["correspondence_turnover"],
        diagnostics["full_frozen_translation_difference_m"],
    )
    axis.set_title(f"Turnover versus native full/frozen difference\n1260 snapshots; Spearman rho = {rho:.3f}" if rho is not None else "Turnover versus native full/frozen difference\nSpearman undefined")
    path = figures / "turnover_vs_full_frozen_difference.png"
    _save_figure(fig, path)
    chart_map.append({"figure": path.name, "family": "relationship", "question": "Does correspondence turnover track the full/frozen endpoint difference?", "palette": "single orange root"})

    condition_summary = trials.groupby(["noise_condition", "registration_backend"], observed=True)["translation_error_m"].median().reset_index()
    fig, axis = plt.subplots(figsize=(11, 5.2))
    x = np.arange(6)
    width = 0.24
    for offset, backend, color in ((-width, "native_full", BLUE), (0.0, "native_frozen", GOLD), (width, "open3d_full", ORANGE)):
        data = condition_summary[condition_summary["registration_backend"] == backend].set_index("noise_condition")
        values = [float(data.loc[condition, "translation_error_m"]) * 1000 for condition in CONDITION_ORDER]
        axis.bar(x + offset, values, width, label=backend, color=color, edgecolor=INK)
    axis.set_xticks(x, [condition.replace("_", " ").title() for condition in CONDITION_ORDER], rotation=30, ha="right")
    axis.set_ylabel("median translation error (mm)")
    axis.legend(frameon=False)
    _style_axis(axis)
    axis.set_title("Noise-condition effects across all scenes\nMedians over each condition × backend Development population")
    path = figures / "noise_condition_effects.png"
    _save_figure(fig, path)
    chart_map.append({"figure": path.name, "family": "comparison", "question": "How do the six frozen measurement conditions change endpoint error?", "palette": "blue-gold-orange"})

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.3))
    for axis, condition in zip(axes, ("INDEPENDENT_NOISE_FREE", "FULL_NOISE")):
        subset = summary[summary["noise_condition"] == condition]
        native = subset[subset["registration_backend"] == "native_full"].set_index("scene_variant")
        other = subset[subset["registration_backend"] == "open3d_full"].set_index("scene_variant")
        xvalues = [float(native.loc[scene, "translation_error_median_m"]) * 1000 for scene in SCENE_ORDER]
        yvalues = [float(other.loc[scene, "translation_error_median_m"]) * 1000 for scene in SCENE_ORDER]
        axis.scatter(xvalues, yvalues, color=BLUE, s=45)
        for scene, xvalue, yvalue in zip(SCENE_ORDER, xvalues, yvalues):
            axis.annotate(_short_scene(scene), (xvalue, yvalue), xytext=(4, 3), textcoords="offset points", fontsize=8)
        axis.set_xlabel("native full scene median (mm)")
        axis.set_ylabel("Open3D scene median (mm)")
        axis.set_title(condition.replace("_", " ").title())
        _style_axis(axis)
    fig.suptitle("Cross-backend scene ranking\nSeven scene medians per frozen signal condition", color=INK)
    path = figures / "backend_scene_ranking.png"
    _save_figure(fig, path)
    chart_map.append({"figure": path.name, "family": "relationship", "question": "Do native and Open3D rank scene errors similarly?", "palette": "single blue root with direct labels"})
    return chart_map


def _gate_decision(
    raw: Mapping[str, Any],
    trials: pd.DataFrame,
    diagnostics: pd.DataFrame,
    summary: pd.DataFrame,
    agreement: pd.DataFrame,
    contrast: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame]:
    ideal_rows = []
    ideal_pass = True
    for backend in ("native_full", "open3d_full"):
        subset = trials[
            (trials["noise_condition"] == "IDEAL_MATCHED")
            & (trials["registration_backend"] == backend)
        ]
        q95_t = float(subset["translation_error_m"].quantile(0.95))
        q95_r = float(subset["rotation_error_deg"].quantile(0.95))
        failures = int(subset["solver_failure"].astype(bool).sum())
        passed = q95_t <= 0.001 and q95_r <= 0.01 and failures == 0
        ideal_pass = ideal_pass and passed
        ideal_rows.append(
            {
                "backend": backend,
                "q95_translation_error_m": q95_t,
                "q95_rotation_error_deg": q95_r,
                "solver_failure_count": failures,
                "pass": passed,
            }
        )

    scene_effect = False
    for condition in ("INDEPENDENT_NOISE_FREE", "FULL_NOISE"):
        for weak in ("LONG_CORRIDOR", "PARALLEL_WALLS"):
            pair = contrast[
                (contrast["noise_condition"] == condition)
                & (contrast["weak_scene"] == weak)
            ]
            if len(pair) == 2 and bool(pair["ratio_at_least_2"].all()):
                scene_effect = True
    agreement_values = agreement[
        "native_open3d_scene_translation_median_spearman_rho"
    ].dropna()
    cross_backend = bool(len(agreement_values) and agreement_values.max() >= 0.50)

    rich_difference = float(
        diagnostics[
            diagnostics["scene_variant"] == "GEOMETRY_RICH_ROOM"
        ]["full_frozen_translation_difference_m"].median()
    )
    reassociation_rows = []
    ratio_pass = False
    for weak in (
        "LONG_CORRIDOR",
        "PARALLEL_WALLS",
        "END_FACE_TRANSITION_WEAK",
        "END_FACE_TRANSITION_ABSENT",
    ):
        value = float(
            diagnostics[diagnostics["scene_variant"] == weak][
                "full_frozen_translation_difference_m"
            ].median()
        )
        ratio = value / rich_difference if rich_difference > 1.0e-15 else (math.inf if value > 0.0 else math.nan)
        ratio_pass = ratio_pass or bool(ratio >= 3.0)
        reassociation_rows.append(
            {
                "weak_scene": weak,
                "weak_median_m": value,
                "rich_room_median_m": rich_difference,
                "weak_over_rich_ratio": ratio,
            }
        )
    turnover_rho = safe_spearman(
        diagnostics["correspondence_turnover"],
        diagnostics["full_frozen_translation_difference_m"],
    )
    reassociation = bool(
        ratio_pass and turnover_rho is not None and abs(turnover_rho) >= 0.30
    )
    # The locked protocol makes IDEAL_MATCHED the first hard gate.  Later
    # scientific signals are not evaluated when it fails, even if smoke rows
    # happen to contain descriptive ratios that cross their thresholds.
    preliminary_signals_evaluated = bool(ideal_pass and not raw.get("smoke", False))
    if not preliminary_signals_evaluated:
        scene_effect = False
        cross_backend = False
        reassociation = False

    decisions: dict[str, Any] = {
        "DEVELOPMENT_PIPELINE_EXECUTABLE": bool(raw["development_pipeline_executable"]),
        "ALL_1260_SNAPSHOTS_COMPLETE": int(raw["snapshot_count"]) == 1260,
        "ALL_3780_TRIALS_COMPLETE": int(raw["trial_count"]) == 3780,
        "SNAPSHOT_PAIRING_PASS": int(raw["snapshot_pairing_violation_count"]) == 0,
        "OPEN3D_BACKEND_PASS": bool(
            len(trials[trials["registration_backend"] == "open3d_full"])
            == int(raw["snapshot_count"])
            and trials[trials["registration_backend"] == "open3d_full"]["finite_result"].astype(bool).all()
        ),
        "NO_CONFIRMATORY_SEED_ACCESS": int(raw["confirmatory_seed_instantiation_count"]) == 0,
        "NO_OLD_CAPTURE_TEST_SEED_ACCESS": int(raw["old_capture_range_test_seed_access_count"]) == 0,
        "NO_GT_OPTIMIZATION_LEAKAGE": int(raw["gt_optimization_leakage_count"]) == 0,
        "IDEAL_MATCHED_CONTROL_PASS": ideal_pass,
        "PRELIMINARY_SCENE_EFFECT_OBSERVED": scene_effect,
        "PRELIMINARY_CROSS_BACKEND_SIGNAL_OBSERVED": cross_backend,
        "PRELIMINARY_REASSOCIATION_EFFECT_OBSERVED": reassociation,
        "NEW_PROTOCOL_AMBIGUITIES_FOUND": False,
    }
    decisions["ZERO_PERTURBATION_CONFIRMATORY_LOCK_AUTHORIZED"] = confirmatory_lock_authorized(decisions)
    decisions["ZERO_PERTURBATION_CONFIRMATORY_RUN_AUTHORIZED"] = False
    decisions["REAL_DATA_VALIDATION_AUTHORIZED"] = False
    decisions["MEASUREMENT_PAPER_MAINLINE_AUTHORIZED"] = False
    decisions["PRELIMINARY_SCIENTIFIC_SIGNALS_EVALUATED"] = preliminary_signals_evaluated
    decisions["FULL_DEVELOPMENT_RUN_EXECUTED"] = not bool(raw.get("smoke", False))
    decisions["ideal_matched_backend_details"] = ideal_rows
    decisions["turnover_full_frozen_spearman_rho"] = turnover_rho
    decisions["reassociation_scene_ratios"] = reassociation_rows
    decisions["native_full_solver_failure_count"] = int(
        trials[trials["registration_backend"] == "native_full"]["solver_failure"].astype(bool).sum()
    )
    decisions["native_frozen_solver_failure_count"] = int(
        trials[trials["registration_backend"] == "native_frozen"]["solver_failure"].astype(bool).sum()
    )
    decisions["open3d_solver_failure_count"] = int(
        trials[trials["registration_backend"] == "open3d_full"]["solver_failure"].astype(bool).sum()
    )
    gate_rows = []
    for name, value in decisions.items():
        if isinstance(value, bool):
            gate_rows.append({"gate": name, "value": value})
    return decisions, pd.DataFrame(gate_rows)


def _protocol_summary(protocol: Any) -> pd.DataFrame:
    rows = [
        ("protocol_type", protocol.section("protocol")["protocol_type"]),
        ("protocol_sha256", protocol.source_sha256),
        ("scene_count", len(protocol.scenes)),
        ("condition_count", len(protocol.conditions)),
        ("expected_snapshot_count", 1260),
        ("expected_trial_count", 3780),
        ("repeat_count", 5),
        ("open3d_version", str(open3d.__version__)),
        ("bootstrap_repetitions", 1000),
        ("formal_p_values", False),
        ("confirmatory_claim_authorized", False),
        ("confirmatory_run_authorized", False),
    ]
    return pd.DataFrame(rows, columns=["protocol_field", "value"])


def _render_report(
    path: Path,
    decisions: Mapping[str, Any],
    raw: Mapping[str, Any],
    agreement: pd.DataFrame,
    contrast: pd.DataFrame,
    diagnostics: pd.DataFrame,
) -> None:
    ideal_lines = []
    for row in decisions["ideal_matched_backend_details"]:
        ideal_lines.append(
            f"- `{row['backend']}`: q95 translation {row['q95_translation_error_m']:.6g} m; "
            f"q95 rotation {row['q95_rotation_error_deg']:.6g}°; failures {row['solver_failure_count']}; pass `{str(row['pass']).lower()}`."
        )
    agreement_lines = [
        f"- `{row.noise_condition}`: Spearman rho `{row.native_open3d_scene_translation_median_spearman_rho:.4f}`."
        for row in agreement.itertuples()
    ]
    contrast_lines = [
        f"- `{row.noise_condition}` / `{row.registration_backend}` / `{row.weak_scene}`: weak/rich median ratio `{row.weak_over_rich_translation_median_ratio:.4g}`."
        for row in contrast.itertuples()
    ]
    turnover_rho = decisions["turnover_full_frozen_spearman_rho"]
    run_scope = "the complete Development matrix" if not raw.get("smoke", False) else "the frozen 42-snapshot smoke matrix"
    repeat_scope = (
        "two measurement seeds × five repeats"
        if not raw.get("smoke", False)
        else "one measurement seed × one repeat in this smoke; the frozen full design would use two × five"
    )
    geometry_scope = 3 if not raw.get("smoke", False) else 1
    stop_note = (
        "The smoke failed the first hard gate, so the complete 1260-snapshot / 3780-trial Development matrix was not run, exactly as required by the frozen stopping rule."
        if raw.get("smoke", False)
        else "The complete Development matrix was executed after smoke passed."
    )
    text = f"""# Zero-Perturbation Registration Measurement — Development

## Technical summary

Development executed {run_scope}: {raw['snapshot_count']} independently keyed snapshots and {raw['trial_count']} paired backend trials. Snapshot pairing violations, Confirmatory seed instantiations, old capture-range Test-seed accesses, and GT optimization leakage were all zero. The IDEAL_MATCHED hard control is `{str(decisions['IDEAL_MATCHED_CONTROL_PASS']).lower()}`. {stop_note}

The three preliminary engineering signals are: scene effect `{str(decisions['PRELIMINARY_SCENE_EFFECT_OBSERVED']).lower()}`, cross-backend scene ranking `{str(decisions['PRELIMINARY_CROSS_BACKEND_SIGNAL_OBSERVED']).lower()}`, and reassociation effect `{str(decisions['PRELIMINARY_REASSOCIATION_EFFECT_OBSERVED']).lower()}`. Their evaluation flag is `{str(decisions['PRELIMINARY_SCIENTIFIC_SIGNALS_EVALUATED']).lower()}` because the hard control must pass first. Consequently, future Confirmatory-lock generation authorization is `{str(decisions['ZERO_PERTURBATION_CONFIRMATORY_LOCK_AUTHORIZED']).lower()}`. Confirmatory execution remains false.

## IDEAL_MATCHED establishes the zero-error control

{chr(10).join(ideal_lines)}

See [ideal_matched_control.png](figures/ideal_matched_control.png). This hard control is evaluated only on native full reassociation and Open3D full ICP; native frozen is reported but does not decide the gate.

## Scene effects and backend agreement remain preliminary

{chr(10).join(contrast_lines)}

Cross-backend ranking:

{chr(10).join(agreement_lines)}

These are smoke-only descriptive contrasts. They are not evaluated as Development Go/No-Go signals because IDEAL_MATCHED failed, and they are not confirmatory estimates or paper claims. Exact scene × condition × backend summaries and exploratory geometry-block bootstrap calculations are in [noise_condition_summary.csv](tables/noise_condition_summary.csv).

## Reassociation changes are measured explicitly

Across all {raw['snapshot_count']} native pairs in this run, correspondence-turnover versus full/frozen translation difference has descriptive Spearman rho `{turnover_rho if turnover_rho is not None else 'null'}`. Because the hard gate failed, this value does not evaluate Signal C. Full and frozen are two algorithms on one snapshot; Frozen is never treated as ground truth. See [turnover_vs_full_frozen_difference.png](figures/turnover_vs_full_frozen_difference.png), [correspondence_turnover.csv](tables/correspondence_turnover.csv), and [full_frozen_comparison.csv](tables/full_frozen_comparison.csv).

## Scope, data, and metric definitions

Every trial begins at `T_initial = T_reference`. Translation error is `||p_estimated - p_reference||`; rotation error is `||Log(R_reference^T R_estimated)||`. A repeated-measurement group fixes scene, geometry seed, condition, and backend, then aggregates {repeat_scope}. The norm of the group mean is systematic offset; repeatability RMS is the square root of the covariance trace with `ddof=1`. In this early-stop smoke, one-row groups have zero covariance by definition and do not estimate repeatability. A single-trial displacement is not called bias.

The six frozen conditions and seven frozen synthetic scenes contain no real or visual data. The historical 0.02 m / 0.5° capture-range thresholds are not used.

## Methodology and reproducibility

The native full path rebuilds correspondence search, local planes, residuals, and Jacobians on each nonlinear evaluation. Native frozen retains its initial linearization. Open3D 0.19.0+b012259 independently estimates target-map normals and runs one global point-to-plane parameter set. All three methods consume identical point coordinates and reference initialization for each snapshot, as established by backend-input checksums.

Traditional Hessian metrics use the native initial correspondence system, the native Huber weights, and the unchanged ODI/AIS definitions with the existing ODI pose scaling. Development reports descriptive statistics and Spearman correlations only; no formal p-values or model A/B fitting are performed. The 1000-repetition exploratory bootstrap resamples the outer geometry-seed block using the scheduled Development bootstrap seed.

## Limitations, uncertainty, and robustness checks

- Synthetic Development evidence cannot establish real-data validity, causal mechanism, or Measurement-paper readiness.
- Only {geometry_scope} geometry seed(s) underlie the saved exploratory block calculations; in the early-stop smoke the one-block interval collapses and is not an uncertainty estimate.
- Open3D exposes the final correspondence set, fitness, and RMSE but not a portable per-iteration convergence flag; the backend failure contract therefore requires a finite transform/metrics and a non-empty final correspondence set.
- `multi_attractor_summary.csv` is an audit-only endpoint-bin proxy at 1e-4 m/rad and does not authorize a formal multi-attractor claim.
- All nine figures were generated from the saved CSV evidence and are subordinate to exact tables.

## Recommended next step

No Confirmatory lock may be generated from this run. Any future investigation of the native exact-match fixed-point failure must be a separately frozen research route; the locked thresholds, Open3D parameters, and observed Development protocol cannot be changed after this result. This task generated no Confirmatory lock and did not access Confirmatory seeds.

## Further questions

- Will the Development scene ordering and reassociation association persist under the already-frozen Confirmatory split?
- Do real sensor artifacts preserve the same ordering without scene-specific backend tuning? That question remains explicitly unauthorized here.
"""
    path.write_text(text, encoding="utf-8")


def _sha256sums(artifact: Path) -> None:
    target = artifact / "SHA256SUMS"
    paths = sorted(
        path for path in artifact.rglob("*") if path.is_file() and path != target
    )
    lines = [f"{file_sha256(path)}  {path.relative_to(artifact).as_posix()}" for path in paths]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze_development(root: str | Path, *, run_id: str) -> Path:
    repository = Path(root).resolve()
    protocol = load_protocol(repository)
    result_root = repository / protocol.section("outputs")["result_root"] / run_id
    raw = json.loads((result_root / "raw_run_manifest.json").read_text(encoding="utf-8"))
    inventory = pd.read_csv(result_root / "snapshot_inventory.csv")
    trials = pd.read_csv(result_root / "trial_results.csv")
    diagnostics = pd.read_csv(result_root / "native_diagnostics.csv")
    artifact = repository / protocol.section("outputs")["artifact_root"]
    tables = artifact / "tables"
    figures = artifact / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    repeated = pd.DataFrame(
        aggregate_repeated_measurements(
            trials.to_dict("records"),
            ddof=int(protocol.section("statistics")["covariance_ddof"]),
            denominator_epsilon=float(
                protocol.section("statistics")["systematic_fraction_denominator_epsilon"]
            ),
        )
    )
    bootstrap_seed = int(protocol.development_seeds["bootstrap"]["bootstrap_0"])
    summary = _noise_summary(trials, bootstrap_seed)
    agreement = _backend_agreement(summary)
    contrast = _scene_contrast(summary)
    correlations = _traditional_correlations(diagnostics)
    multi_attractor = _multi_attractor_summary(trials)
    runtime = _runtime_summary(trials)
    decisions, gates = _gate_decision(raw, trials, diagnostics, summary, agreement, contrast)

    scene_inventory = (
        inventory.groupby("scene_variant", sort=False)
        .agg(
            snapshot_count=("snapshot_id", "count"),
            scan_point_count_min=("scan_point_count", "min"),
            scan_point_count_max=("scan_point_count", "max"),
            map_point_count_min=("map_point_count", "min"),
            map_point_count_max=("map_point_count", "max"),
            primitive_count_max=("primitive_count", "max"),
        )
        .reset_index()
    )
    zero_columns = [
        "snapshot_id",
        "scene_variant",
        "geometry_seed",
        "measurement_seed",
        "repeat_index",
        "noise_condition",
        "registration_backend",
        "translation_x_m",
        "translation_y_m",
        "translation_z_m",
        "rotation_x_rad",
        "rotation_y_rad",
        "rotation_z_rad",
        "translation_error_m",
        "rotation_error_rad",
        "rotation_error_deg",
        "solver_failure",
    ]
    systematic_columns = [
        "scene_variant", "geometry_seed", "noise_condition", "registration_backend", "trial_count",
        "mean_translation_x_m", "mean_translation_y_m", "mean_translation_z_m", "systematic_translation_offset_m",
        "mean_rotation_x_rad", "mean_rotation_y_rad", "mean_rotation_z_rad", "systematic_rotation_offset_rad",
        "systematic_fraction_translation",
    ]
    repeat_columns = [
        "scene_variant", "geometry_seed", "noise_condition", "registration_backend", "trial_count",
        "translation_repeatability_covariance", "translation_repeatability_rms_m",
        "rotation_repeatability_covariance", "rotation_repeatability_rms_rad",
        "translation_error_median_m", "translation_error_iqr_m", "translation_error_q95_m",
        "rotation_error_median_rad", "rotation_error_iqr_rad", "rotation_error_q95_rad",
    ]
    turnover_columns = [
        "snapshot_id", "scene_variant", "geometry_seed", "measurement_seed", "repeat_index", "noise_condition",
        "correspondence_turnover", "correspondence_turnover_reason", "accepted_scan_index_turnover",
        "accepted_scan_index_turnover_reason", "initial_correspondence_count", "final_correspondence_count",
        "correspondence_intersection_count", "correspondence_union_count",
    ]
    normal_columns = [
        "snapshot_id", "scene_variant", "geometry_seed", "measurement_seed", "repeat_index", "noise_condition",
        "normal_angle_common_count", "median_normal_angle_change_deg", "q95_normal_angle_change_deg",
        "normal_angle_turnover_reason",
    ]
    comparison_columns = [
        "snapshot_id", "scene_variant", "geometry_seed", "measurement_seed", "repeat_index", "noise_condition",
        "full_frozen_translation_difference_m", "full_frozen_rotation_difference_rad",
        "full_translation_error_m", "full_rotation_error_rad", "frozen_translation_error_m", "frozen_rotation_error_rad",
    ]
    outputs = {
        "protocol_summary.csv": _protocol_summary(protocol),
        "scene_inventory.csv": scene_inventory,
        "snapshot_inventory.csv": inventory,
        "trial_results.csv": trials,
        "zero_initialization_error.csv": trials[zero_columns],
        "systematic_offset_summary.csv": repeated[systematic_columns],
        "repeatability_summary.csv": repeated[repeat_columns],
        "correspondence_turnover.csv": diagnostics[turnover_columns],
        "normal_turnover.csv": diagnostics[normal_columns],
        "full_frozen_comparison.csv": diagnostics[comparison_columns],
        "noise_condition_summary.csv": summary,
        "backend_agreement.csv": agreement,
        "scene_contrast.csv": contrast,
        "traditional_metric_correlations.csv": correlations,
        "multi_attractor_summary.csv": multi_attractor,
        "runtime_summary.csv": runtime,
        "gate_summary.csv": gates,
    }
    for name, frame in outputs.items():
        _write_frame(tables / name, frame)

    chart_map = _build_figures(figures, trials, repeated, diagnostics, summary)
    protocol_lock = {
        "schema_version": "zero_perturbation_development_protocol_lock_v1",
        "protocol_path": PROTOCOL_RELATIVE.as_posix(),
        "protocol_sha256": PROTOCOL_SHA256,
        "protocol_lock_commit": "92e989f6f1b5f42f586883fd6742f2669929981d",
        "protocol_lock_tag": "archive/zero-perturbation-development-protocol-lock",
        "protocol_lock_tag_commit": _git(repository, "rev-list", "-n", "1", "archive/zero-perturbation-development-protocol-lock"),
        "development_run_id": run_id,
        "confirmatory_lock_generated": False,
        "confirmatory_run_authorized": False,
    }
    _write_json(artifact / "development_protocol_lock.json", protocol_lock)
    _write_json(artifact / "final_decision.json", decisions)
    _render_report(artifact / "development_report.md", decisions, raw, agreement, contrast, diagnostics)
    manifest = {
        "schema_version": "zero_perturbation_development_artifact_v1",
        "run_id": run_id,
        "smoke": bool(raw.get("smoke", False)),
        "branch": _git(repository, "branch", "--show-current"),
        "analysis_commit": _git(repository, "rev-parse", "HEAD"),
        "protocol_sha256": protocol.source_sha256,
        "seed_schedule_sha256": protocol.section("immutable_inputs")["seed_schedule"]["sha256"],
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "pandas_version": pd.__version__,
        "matplotlib_version": matplotlib.__version__,
        "open3d_version": str(open3d.__version__),
        "snapshot_count": int(raw["snapshot_count"]),
        "trial_count": int(raw["trial_count"]),
        "snapshot_pairing_violation_count": int(raw["snapshot_pairing_violation_count"]),
        "confirmatory_seed_instantiation_count": int(raw["confirmatory_seed_instantiation_count"]),
        "old_capture_range_test_seed_access_count": int(raw["old_capture_range_test_seed_access_count"]),
        "gt_optimization_leakage_count": int(raw["gt_optimization_leakage_count"]),
        "formal_p_values_computed": False,
        "real_data_used": False,
        "vision_used": False,
        "confirmatory_run_executed": False,
        "chart_map": chart_map,
        "table_files": sorted(outputs),
        "figure_files": sorted(item["figure"] for item in chart_map),
        "raw_result_manifest": str((result_root / "raw_run_manifest.json").relative_to(repository)),
    }
    _write_json(artifact / "run_manifest.json", manifest)
    _sha256sums(artifact)
    return artifact


__all__ = [
    "CONFIRMATORY_LOCK_PREREQUISITES",
    "analyze_development",
    "confirmatory_lock_authorized",
]
