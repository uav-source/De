"""Offline-only paired causal consistency summaries for Day 13."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Mapping, Sequence

import numpy as np


def harmful_update_metrics(row: Mapping[str, Any]) -> Mapping[str, Any]:
    """Classify one already-completed estimator update using offline GT fields."""

    alignment = float(row["applied_update_weak_signed_m"]) * float(
        row["prior_online_weak_error_signed_m"]
    )
    points_with_error = alignment > 0.0
    worsened = float(row["online_weak_abs_error_reduction_m"]) < 0.0
    return {
        "update_error_alignment": alignment,
        "update_points_with_error": bool(points_with_error),
        "online_weak_error_worsened": bool(worsened),
        "harmful_update_frame": bool(points_with_error and worsened),
    }


def build_causal_consistency(
    merged_rows: Sequence[Mapping[str, Any]],
) -> Sequence[Mapping[str, Any]]:
    """Compare eligible matched clean/coherent active frames per geometry/sweep."""

    index = {}
    for row in merged_rows:
        if str(row.get("role", "evaluation")) != "evaluation":
            continue
        if str(row.get("sweep")) not in {"geometry", "observation"}:
            continue
        if not _eligible(row):
            continue
        key = tuple(row[field] for field in (
            "sweep", "level", "geometry_seed", "sensor_seed", "process_seed", "frame_index"
        ))
        index[(str(row["stress"]),) + key] = row
    groups = defaultdict(list)
    for key, coherent in index.items():
        if key[0] != "coherent_subhuber_slip" or not bool(coherent.get("stress_active")):
            continue
        clean = index.get(("clean",) + key[1:])
        if clean is None:
            continue
        groups[(int(coherent["geometry_seed"]), str(coherent["sweep"]))].append(
            (clean, coherent)
        )
    output = []
    for (geometry_seed, sweep), pairs in sorted(groups.items()):
        clean_harmful = [harmful_update_metrics(clean)["harmful_update_frame"] for clean, _ in pairs]
        coherent_harmful = [
            harmful_update_metrics(coherent)["harmful_update_frame"] for _, coherent in pairs
        ]
        axis_changes = np.asarray(
            [float(coherent["axis_abs_error_change_m"]) for _, coherent in pairs], dtype=float
        )
        weak_reductions = np.asarray(
            [float(coherent["online_weak_abs_error_reduction_m"]) for _, coherent in pairs],
            dtype=float,
        )
        clean_fraction = float(np.mean(clean_harmful))
        coherent_fraction = float(np.mean(coherent_harmful))
        output.append({
            "geometry_seed": geometry_seed,
            "sweep": sweep,
            "matched_frame_count": len(pairs),
            "clean_harmful_fraction": clean_fraction,
            "coherent_harmful_fraction": coherent_fraction,
            "paired_harmful_fraction_difference": coherent_fraction - clean_fraction,
            "median_axis_abs_error_change_m": float(np.median(axis_changes)),
            "fraction_axis_error_worsened": float(np.mean(axis_changes > 0.0)),
            "median_online_weak_abs_error_reduction_m": float(np.median(weak_reductions)),
            "offline_evaluation_only": True,
        })
    for sweep in ("geometry", "observation"):
        if len([row for row in output if row["sweep"] == sweep]) != 10:
            raise ValueError(f"Day 13 causal summary lost an evaluation geometry: {sweep}")
    return output


def _eligible(row: Mapping[str, Any]) -> bool:
    try:
        score = float(row["huber_cusum_max"])
        weak = float(row["prior_online_weak_error_signed_m"])
    except (KeyError, TypeError, ValueError):
        return False
    return bool(
        row.get("stat_input_valid")
        and row.get("window_ready")
        and math.isfinite(score)
        and math.isfinite(weak)
    )
