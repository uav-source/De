"""Explicit correspondence and plane-normal turnover measurements."""

from __future__ import annotations

from typing import Any

import numpy as np


def correspondence_keys(
    accepted_scan_indices: np.ndarray, neighbor_indices: np.ndarray
) -> set[tuple[int, tuple[int, ...]]]:
    accepted = np.asarray(accepted_scan_indices, dtype=np.int64)
    neighbors = np.asarray(neighbor_indices, dtype=np.int64)
    if accepted.ndim != 1 or neighbors.ndim != 2 or neighbors.shape[0] != accepted.size:
        raise ValueError("correspondence arrays have incompatible shapes")
    return {
        (int(scan_index), tuple(sorted(int(value) for value in row)))
        for scan_index, row in zip(accepted, neighbors)
    }


def jaccard_turnover(initial: set[Any], final: set[Any]) -> tuple[float | None, str]:
    union = initial | final
    if not union:
        return None, "EMPTY_CORRESPONDENCE_UNION"
    return 1.0 - len(initial & final) / len(union), ""


def correspondence_turnover(initial_evaluation: Any, final_evaluation: Any) -> dict[str, Any]:
    initial_keys = correspondence_keys(
        initial_evaluation.accepted_scan_indices, initial_evaluation.neighbor_indices
    )
    final_keys = correspondence_keys(
        final_evaluation.accepted_scan_indices, final_evaluation.neighbor_indices
    )
    turnover, reason = jaccard_turnover(initial_keys, final_keys)
    initial_indices = set(int(value) for value in initial_evaluation.accepted_scan_indices)
    final_indices = set(int(value) for value in final_evaluation.accepted_scan_indices)
    index_turnover, index_reason = jaccard_turnover(initial_indices, final_indices)
    return {
        "correspondence_turnover": turnover,
        "correspondence_turnover_reason": reason,
        "accepted_scan_index_turnover": index_turnover,
        "accepted_scan_index_turnover_reason": index_reason,
        "initial_correspondence_count": len(initial_keys),
        "final_correspondence_count": len(final_keys),
        "correspondence_intersection_count": len(initial_keys & final_keys),
        "correspondence_union_count": len(initial_keys | final_keys),
    }


def normal_angle_turnover(initial_evaluation: Any, final_evaluation: Any) -> dict[str, Any]:
    initial = {
        int(index): np.asarray(normal, dtype=np.float64)
        for index, normal in zip(
            initial_evaluation.accepted_scan_indices, initial_evaluation.plane_normals
        )
    }
    final = {
        int(index): np.asarray(normal, dtype=np.float64)
        for index, normal in zip(
            final_evaluation.accepted_scan_indices, final_evaluation.plane_normals
        )
    }
    common = sorted(set(initial) & set(final))
    if not common:
        return {
            "normal_angle_common_count": 0,
            "median_normal_angle_change_deg": None,
            "q95_normal_angle_change_deg": None,
            "normal_angle_turnover_reason": "NO_COMMON_ACCEPTED_SCAN_INDEX",
        }
    angles = []
    for index in common:
        left = initial[index] / np.linalg.norm(initial[index])
        right = final[index] / np.linalg.norm(final[index])
        # Plane orientation is axial: n and -n describe the same local plane.
        cosine = float(np.clip(abs(np.dot(left, right)), 0.0, 1.0))
        angles.append(float(np.degrees(np.arccos(cosine))))
    values = np.asarray(angles, dtype=np.float64)
    return {
        "normal_angle_common_count": len(common),
        "median_normal_angle_change_deg": float(np.median(values)),
        "q95_normal_angle_change_deg": float(np.quantile(values, 0.95)),
        "normal_angle_turnover_reason": "",
    }


__all__ = [
    "correspondence_keys",
    "correspondence_turnover",
    "jaccard_turnover",
    "normal_angle_turnover",
]
