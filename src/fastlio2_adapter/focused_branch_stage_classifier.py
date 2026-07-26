"""Focused scan 155-205 formal stage classification."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Mapping, Sequence

from . import experiment_a_map_snapshot_coherence as map_coherence
from . import experiment_a_stage_hash as stage_hash


SCAN_START = 155
SCAN_END = 205
EXPECTED_RECORD_COUNT = 51
EXPECTED_SNAPSHOTS_PER_RUN = 102

STAGE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("timestamp", ("timestamp_begin", "timestamp_end")),
    ("raw_lidar", ("raw_lidar_payload_checksum",)),
    ("imu_bundle", ("imu_bundle_checksum",)),
    ("undistorted_cloud", ("undistorted_cloud_checksum",)),
    ("prior_state", ("prior_state_checksum",)),
    ("prior_covariance", ("prior_covariance_checksum",)),
    ("map_content_before", ("map_content_before_measurement",)),
    ("map_traversal_before", ("map_traversal_before_measurement",)),
    ("accepted_indices", ("accepted_index_checksum",)),
    ("formal_correspondence", (
        "valid_correspondence_count",
        "formal_correspondence_checksum",
    )),
    ("formal_j_h_residual", (
        "formal_native_jacobian_checksum",
        "detector_jacobian_checksum",
        "formal_innovation_checksum",
        "geometric_residual_checksum",
    )),
    ("post_update_state", (
        "post_update_state_checksum",
        "post_update_covariance_checksum",
    )),
    ("insertion_batch", (
        "map_insertion_executed",
        "map_insertion_batch_ordered_checksum",
        "map_insertion_batch_multiset_checksum",
        "map_insertion_batch_point_count",
    )),
    ("map_content_after", ("map_content_after_insertion",)),
    ("map_traversal_after", ("map_traversal_after_insertion",)),
)

FORMAL_GROUPS = {
    "prior_state",
    "prior_covariance",
    "map_content_before",
    "accepted_indices",
    "formal_correspondence",
    "formal_j_h_residual",
    "post_update_state",
    "insertion_batch",
    "map_content_after",
}


class FocusedStageError(ValueError):
    """Focused stage evidence is missing, incoherent, or misaligned."""


def configure_focused_contract() -> None:
    """Apply the authorized runtime window to existing V2 validators."""

    stage_hash.SCAN_START = SCAN_START
    stage_hash.SCAN_END = SCAN_END
    stage_hash.EXPECTED_RECORD_COUNT = EXPECTED_RECORD_COUNT
    map_coherence.SCAN_START = SCAN_START
    map_coherence.SCAN_END = SCAN_END
    map_coherence.EXPECTED_RECORD_COUNT = EXPECTED_RECORD_COUNT
    map_coherence.EXPECTED_SNAPSHOTS_PER_RUN = EXPECTED_SNAPSHOTS_PER_RUN
    map_coherence.EXPECTED_TOTAL_SNAPSHOTS = (
        2 * EXPECTED_SNAPSHOTS_PER_RUN
    )


@contextmanager
def focused_contract():
    """Temporarily apply the authorized window without polluting callers."""

    stage_previous = {
        "SCAN_START": stage_hash.SCAN_START,
        "SCAN_END": stage_hash.SCAN_END,
        "EXPECTED_RECORD_COUNT": stage_hash.EXPECTED_RECORD_COUNT,
    }
    coherence_previous = {
        "SCAN_START": map_coherence.SCAN_START,
        "SCAN_END": map_coherence.SCAN_END,
        "EXPECTED_RECORD_COUNT": map_coherence.EXPECTED_RECORD_COUNT,
        "EXPECTED_SNAPSHOTS_PER_RUN": (
            map_coherence.EXPECTED_SNAPSHOTS_PER_RUN
        ),
        "EXPECTED_TOTAL_SNAPSHOTS": (
            map_coherence.EXPECTED_TOTAL_SNAPSHOTS
        ),
    }
    configure_focused_contract()
    try:
        yield
    finally:
        for name, value in stage_previous.items():
            setattr(stage_hash, name, value)
        for name, value in coherence_previous.items():
            setattr(map_coherence, name, value)


def load_focused_records(path: Any) -> list[dict[str, Any]]:
    with focused_contract():
        value = __import__("json").loads(path.read_text(encoding="utf-8"))
        records = [stage_hash.validate_record(row) for row in value]
    scans = [int(row["scan_index"]) for row in records]
    if scans != list(range(SCAN_START, SCAN_END + 1)):
        raise FocusedStageError("focused stage window coverage mismatch")
    return records


def _same(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    fields: Sequence[str],
) -> bool:
    return all(left[field] == right[field] for field in fields)


def _classify(
    rows: Sequence[Mapping[str, Any]],
    scan: int | None,
    stage: str | None,
) -> str:
    if scan is None or stage is None:
        return "NO_FORMAL_DIVERGENCE"
    through = [row for row in rows if int(row["scan_index"]) <= scan]
    if any(
        not row["raw_lidar_identity"] or not row["imu_bundle_identity"]
        for row in through
    ):
        return "INPUT_STAGE_DIVERGED"
    if any(not row["undistorted_cloud_identity"] for row in through):
        return "UNDISTORTION_OR_IMU_PROCESSING_STAGE_DIVERGED"
    if stage in {"prior_state", "prior_covariance"}:
        return "EVIDENCE_GAP"
    if stage == "map_content_before":
        return "MAP_STATE_ALREADY_DIVERGED"
    if stage in {
        "accepted_indices",
        "formal_correspondence",
        "formal_j_h_residual",
    }:
        same_scan = next(row for row in rows if row["scan_index"] == scan)
        if not same_scan["map_traversal_before_identity"]:
            return (
                "IKDTREE_TRAVERSAL_ORDER_ASSOCIATED_"
                "CORRESPONDENCE_DIVERGENCE"
            )
        return (
            "CORRESPONDENCE_CONSTRUCTION_DIVERGED_WITH_"
            "MATCHED_INPUT_AND_MAP_CONTENT"
        )
    if stage == "post_update_state":
        return "FILTER_UPDATE_STAGE_DIVERGED"
    if stage in {"insertion_batch", "map_content_after"}:
        return "MAP_INSERTION_STAGE_DIVERGED"
    return "EVIDENCE_GAP"


def compare_focused_pair(
    *,
    pair: str,
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    with focused_contract():
        expected = list(range(SCAN_START, SCAN_END + 1))
        if [int(row["scan_index"]) for row in left] != expected:
            raise FocusedStageError("left focused window incomplete")
        if [int(row["scan_index"]) for row in right] != expected:
            raise FocusedStageError("right focused window incomplete")
        coherence = map_coherence.pair_coherence_gate(left, right)
    if not (
        coherence["map_snapshot_coherence_pass"]
        and coherence["map_snapshot_cross_scan_coherence_pass"]
    ):
        return {
            "pair": pair,
            "comparison_pass": False,
            "evidence_gap": True,
            "stage_classification_complete": False,
            "stage_classification": "EVIDENCE_GAP",
            "formal_branch_reproduced": False,
            "rows": [],
            **coherence,
        }
    rows = []
    first_formal_scan = None
    first_formal_stage = None
    for left_row, right_row in zip(left, right):
        row: dict[str, Any] = {
            "pair": pair,
            "scan_index": int(left_row["scan_index"]),
        }
        for name, fields in STAGE_GROUPS:
            row[f"{name}_identity"] = _same(left_row, right_row, fields)
        differences = [
            name
            for name, _fields in STAGE_GROUPS
            if not row[f"{name}_identity"]
        ]
        formal = [name for name in differences if name in FORMAL_GROUPS]
        row["first_differing_stage_in_scan"] = (
            differences[0] if differences else ""
        )
        row["first_formal_differing_stage_in_scan"] = (
            formal[0] if formal else ""
        )
        row["formal_divergence_in_scan"] = bool(formal)
        if first_formal_scan is None and formal:
            first_formal_scan = row["scan_index"]
            first_formal_stage = formal[0]
        rows.append(row)
    classification = _classify(
        rows, first_formal_scan, first_formal_stage
    )
    previous = None
    if first_formal_scan is not None:
        previous = next(
            (row for row in rows if row["scan_index"] == first_formal_scan - 1),
            None,
        )
    previous_identity = {
        "pair": pair,
        "first_divergence_scan": first_formal_scan,
        "previous_scan": (
            first_formal_scan - 1 if first_formal_scan is not None else None
        ),
        "previous_timestamp_equal": (
            previous["timestamp_identity"] if previous else None
        ),
        "previous_raw_lidar_equal": (
            previous["raw_lidar_identity"] if previous else None
        ),
        "previous_imu_equal": (
            previous["imu_bundle_identity"] if previous else None
        ),
        "previous_undistorted_equal": (
            previous["undistorted_cloud_identity"] if previous else None
        ),
        "previous_prior_equal": (
            previous["prior_state_identity"]
            and previous["prior_covariance_identity"]
            if previous else None
        ),
        "previous_map_content_before_equal": (
            previous["map_content_before_identity"] if previous else None
        ),
        "previous_correspondence_equal": (
            previous["accepted_indices_identity"]
            and previous["formal_correspondence_identity"]
            and previous["formal_j_h_residual_identity"]
            if previous else None
        ),
        "previous_post_update_equal": (
            previous["post_update_state_identity"] if previous else None
        ),
        "previous_map_content_after_equal": (
            previous["map_content_after_identity"] if previous else None
        ),
    }
    checked = [value for key, value in previous_identity.items()
               if key.startswith("previous_") and key != "previous_scan"]
    previous_pass = (
        all(value is True for value in checked)
        if first_formal_scan is not None
        else True
    )
    if first_formal_scan is not None and not previous_pass:
        classification = "EVIDENCE_GAP"
    return {
        "pair": pair,
        "comparison_pass": True,
        "evidence_gap": classification == "EVIDENCE_GAP",
        "stage_classification_complete": classification != "EVIDENCE_GAP",
        "stage_classification": classification,
        "formal_branch_reproduced": first_formal_scan is not None,
        "first_formal_divergence_scan": first_formal_scan,
        "first_formal_divergence_stage": first_formal_stage or "NONE",
        "previous_scan_identity_pass": previous_pass,
        "previous_scan_identity": previous_identity,
        "identity_status": {
            name: (
                "MATCHED_BY_CANONICAL_CHECKSUM"
                if all(row[f"{name}_identity"] for row in rows)
                else "DIVERGED"
            )
            for name, _fields in STAGE_GROUPS
        },
        "rows": rows,
        **coherence,
    }
