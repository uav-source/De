"""Bounded hypothesis matrix for the Day 6 branch-divergence audit."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


HYPOTHESIS_STATUSES = {
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "CONTRADICTED",
    "PLAUSIBLE_UNPROVEN",
    "NOT_OBSERVABLE",
}
CONFIDENCE_LEVELS = {"HIGH", "MEDIUM", "LOW", "NONE"}
HYPOTHESIS_IDS = (
    "H1_SENSOR_TIMESTAMP_OR_ORDER_MISMATCH",
    "H2_RAW_SENSOR_PAYLOAD_MISMATCH",
    "H3_PRIOR_STATE_DIVERGENCE_PRECEDES_MEASUREMENT",
    "H4_CORRESPONDENCE_SELECTION_DIVERGENCE",
    "H5_MAP_CONTENT_OR_INSERTION_ORDER_DIVERGENCE",
    "H6_OPENMP_OR_THREAD_SCHEDULING_SENSITIVITY",
    "H7_IKDTREE_ORDER_SENSITIVITY",
    "H8_PRODUCTION_DETECTOR_NONDETERMINISM",
    "H9_NEAR_MULTIPLE_EIGENVALUES_EXPLAIN_WEAK_VECTOR_JUMPS",
    "H10_FULL_WEAK_SUBSPACE_IS_STABLE_DESPITE_V1_ROTATION",
)


class Day6HypothesisError(ValueError):
    """A hypothesis row exceeded the permitted evidence vocabulary."""


def validate_hypothesis_rows(
    rows: Sequence[Mapping[str, Any]],
) -> None:
    identifiers = [str(row.get("hypothesis_id")) for row in rows]
    if identifiers != list(HYPOTHESIS_IDS):
        raise Day6HypothesisError("hypothesis identifiers/order mismatch")
    for row in rows:
        if row.get("status") not in HYPOTHESIS_STATUSES:
            raise Day6HypothesisError("invalid hypothesis status")
        if row.get("confidence") not in CONFIDENCE_LEVELS:
            raise Day6HypothesisError("invalid hypothesis confidence")
        for key in (
            "hypothesis",
            "supporting_evidence",
            "contradicting_evidence",
            "missing_evidence",
            "allowed_conclusion",
        ):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise Day6HypothesisError(
                    f"hypothesis field must be non-empty: {key}"
                )


def build_hypothesis_rows(
    facts: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Build fixed H1-H10 conclusions without probabilistic overclaiming."""

    near_status = str(
        facts.get(
            "near_multiple_status",
            "WEAK_DESCRIPTIVE_ASSOCIATION_NO_EXTREME_NEAR_MULTIPLES",
        )
    )
    subspace_status = str(
        facts.get(
            "weak_subspace_status",
            "RELATIVELY_MORE_STABLE_BUT_NOT_UNIFORMLY_STABLE",
        )
    )
    rows = [
        {
            "hypothesis_id": HYPOTHESIS_IDS[0],
            "hypothesis": "Recorded sensor timestamp or ordering mismatch initiated the branch.",
            "supporting_evidence": "No direct supporting trace is present.",
            "contradicting_evidence": "Frozen scan indices and begin/end timestamps remain identical across runs.",
            "missing_evidence": "Raw callback-order and payload identity traces are absent.",
            "status": "PLAUSIBLE_UNPROVEN",
            "confidence": "LOW",
            "allowed_conclusion": "No mismatch is visible in recorded timestamps; unrecorded ordering cannot be excluded.",
        },
        {
            "hypothesis_id": HYPOTHESIS_IDS[1],
            "hypothesis": "A raw sensor payload mismatch initiated the branch.",
            "supporting_evidence": "None at raw-payload granularity.",
            "contradicting_evidence": "Bag identity and callback counts match.",
            "missing_evidence": "Raw LiDAR and IMU-bundle checksums are not recorded.",
            "status": "NOT_OBSERVABLE",
            "confidence": "NONE",
            "allowed_conclusion": "Raw payload identity is not proven.",
        },
        {
            "hypothesis_id": HYPOTHESIS_IDS[2],
            "hypothesis": "Prior state divergence preceded measurement/correspondence divergence.",
            "supporting_evidence": "Prior fields do diverge on the next record.",
            "contradicting_evidence": "At the first branch record the prior remains equal while J, h, valid count, residual and correspondence checksums differ.",
            "missing_evidence": "No missing field changes the observed record-level order.",
            "status": "CONTRADICTED",
            "confidence": "HIGH",
            "allowed_conclusion": "Prior-state divergence does not precede the first recorded measurement-side divergence.",
        },
        {
            "hypothesis_id": HYPOTHESIS_IDS[3],
            "hypothesis": "Correspondence selection or its formal measurement representation diverged at onset.",
            "supporting_evidence": "Valid count, J/h arrays, residual, accepted-index checksum and formal-correspondence checksum first diverge together.",
            "contradicting_evidence": "The full accepted-index and plane arrays are unavailable.",
            "missing_evidence": "Specific point, plane and nearest-neighbor identities are not recorded.",
            "status": "SUPPORTED",
            "confidence": "HIGH",
            "allowed_conclusion": "The formal measurement/correspondence representation diverged; the responsible element is not localized.",
        },
        {
            "hypothesis_id": HYPOTHESIS_IDS[4],
            "hypothesis": "Map content or insertion order initiated the branch.",
            "supporting_evidence": "The map and correspondence path is statically upstream of formal measurement construction.",
            "contradicting_evidence": "No map-level runtime identity evidence is present.",
            "missing_evidence": "Map-content, pre/post insertion and insertion-order checksums are absent.",
            "status": "NOT_OBSERVABLE",
            "confidence": "NONE",
            "allowed_conclusion": "Map causality is not proven.",
        },
        {
            "hypothesis_id": HYPOTHESIS_IDS[5],
            "hypothesis": "OpenMP or thread scheduling sensitivity initiated the branch.",
            "supporting_evidence": "The correspondence search loop is statically parallelized and writes index-owned shared arrays.",
            "contradicting_evidence": "No direct runtime scheduling failure or conflicting write is recorded.",
            "missing_evidence": "OpenMP schedule and thread-identity traces are absent.",
            "status": "PLAUSIBLE_UNPROVEN",
            "confidence": "LOW",
            "allowed_conclusion": "Scheduling sensitivity remains a testable mechanism, not a proven data race.",
        },
        {
            "hypothesis_id": HYPOTHESIS_IDS[6],
            "hypothesis": "ikd-tree ordering sensitivity initiated the branch.",
            "supporting_evidence": "Nearest-neighbor search and incremental insertion are statically on the upstream path.",
            "contradicting_evidence": "No tree-content or operation-order identity is available.",
            "missing_evidence": "Tree content, insertion batches and neighbor identities are absent.",
            "status": "PLAUSIBLE_UNPROVEN",
            "confidence": "LOW",
            "allowed_conclusion": "ikd-tree order sensitivity is not proven.",
        },
        {
            "hypothesis_id": HYPOTHESIS_IDS[7],
            "hypothesis": "Production detector nondeterminism created the observed FAST branch.",
            "supporting_evidence": "None.",
            "contradicting_evidence": "The branch exists in frozen FAST-produced observations before post-replay detector processing; same-input r1/r2 outputs agree.",
            "missing_evidence": "No missing detector evidence is needed to order detector processing after observation capture.",
            "status": "CONTRADICTED",
            "confidence": "HIGH",
            "allowed_conclusion": "Post-replay detector execution is not the source of the FAST observation branch.",
        },
        {
            "hypothesis_id": HYPOTHESIS_IDS[8],
            "hypothesis": "Small lambda1-lambda2 separation is associated with weak-vector jumps.",
            "supporting_evidence": f"Observed status: {near_status}; smaller observed gap bins have larger descriptive vector angles.",
            "contradicting_evidence": "No records enter the two most extreme fixed near-multiple bins, and association is modest.",
            "missing_evidence": "A broader controlled perturbation sample is absent.",
            "status": "PARTIALLY_SUPPORTED",
            "confidence": "MEDIUM",
            "allowed_conclusion": "A descriptive association is present, not a cause of the FAST branch.",
        },
        {
            "hypothesis_id": HYPOTHESIS_IDS[9],
            "hypothesis": "The two-dimensional weak subspace is stable despite v1 rotation.",
            "supporting_evidence": f"Observed status: {subspace_status}; median and p95 subspace angles are smaller than v1 angles.",
            "contradicting_evidence": "Large subspace changes still occur in the tail.",
            "missing_evidence": "No hard stability threshold is authorized.",
            "status": "PARTIALLY_SUPPORTED",
            "confidence": "MEDIUM",
            "allowed_conclusion": "The 2-D subspace is relatively more stable, but uniform stability is not demonstrated.",
        },
    ]
    validate_hypothesis_rows(rows)
    return rows
