"""Strict, identity-keyed alignment for the final Day 8 replay batch."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Mapping, Sequence


STRICT_QUERY_IDENTITY_SCHEMA_VERSION = "day8_strict_query_identity_v2"
IDENTITY_FIELDS = (
    "scan_index",
    "map_mutation_call_index",
    "batch_id",
    "batch_point_index",
    "candidate_point_sha256",
    "voxel_identity",
    "query_box_checksum",
)


def strict_query_identity(row: Mapping[str, Any]) -> tuple[Any, ...]:
    """Return the only query identity authorized for the final batch."""
    return (
        int(row["scan_index"]),
        int(row["map_mutation_call_index"]),
        str(row["batch_id"]),
        int(row["batch_point_index"]),
        str(row["candidate_point_sha256"]),
        str(row["voxel_identity"]),
        int(row["query_box_checksum"]),
    )


def identity_document(identity: Sequence[Any]) -> dict[str, Any]:
    return dict(zip(IDENTITY_FIELDS, identity))


def identity_key(identity: Sequence[Any]) -> str:
    return json.dumps(list(identity), separators=(",", ":"), ensure_ascii=True)


def identity_sha256(identity: Sequence[Any]) -> str:
    return hashlib.sha256(identity_key(identity).encode("utf-8")).hexdigest()


def _unique_index(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[tuple[Any, ...]], dict[tuple[Any, ...], Mapping[str, Any]]]:
    stream: list[tuple[Any, ...]] = []
    indexed: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    for row in rows:
        identity = strict_query_identity(row)
        if identity in indexed:
            raise ValueError("duplicate strict query identity")
        stream.append(identity)
        indexed[identity] = row
    return stream, indexed


def align_strict_query_streams(
    left_rows: Sequence[Mapping[str, Any]],
    right_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Align by identity, while separately reporting stream-order divergence."""
    left_stream, left_index = _unique_index(left_rows)
    right_stream, right_index = _unique_index(right_rows)
    prefix = 0
    for left, right in zip(left_stream, right_stream):
        if left != right:
            break
        prefix += 1
    stream_equal = left_stream == right_stream
    first_stream_divergence = None
    if not stream_equal:
        left_identity = (
            left_stream[prefix] if prefix < len(left_stream) else None
        )
        right_identity = (
            right_stream[prefix] if prefix < len(right_stream) else None
        )
        first_stream_divergence = {
            "stream_index": prefix,
            "left_identity": (
                identity_document(left_identity)
                if left_identity is not None else None
            ),
            "right_identity": (
                identity_document(right_identity)
                if right_identity is not None else None
            ),
        }
    common = set(left_index) & set(right_index)
    ordered_common = [identity for identity in left_stream if identity in common]
    left_only = [identity for identity in left_stream if identity not in common]
    right_only = [
        identity for identity in right_stream if identity not in common
    ]
    classification = (
        "NO_STRICT_QUERY_IDENTITY_OVERLAP"
        if not common else
        "QUERY_STREAM_IDENTITY_DIVERGED"
        if not stream_equal else
        "STRICT_QUERY_IDENTITY_STREAM_EQUAL"
    )
    return {
        "schema_version": STRICT_QUERY_IDENTITY_SCHEMA_VERSION,
        "left_identity_count": len(left_stream),
        "right_identity_count": len(right_stream),
        "common_identity_count": len(common),
        "left_only_identity_count": len(left_only),
        "right_only_identity_count": len(right_only),
        "aligned_prefix_length": prefix,
        "first_identity_stream_divergence": first_stream_divergence,
        "identity_stream_equal": stream_equal,
        "identity_stream_classification": classification,
        "strict_identity_intersection": [
            identity_document(identity) for identity in ordered_common
        ],
        "identity_only_left": [
            identity_document(identity) for identity in left_only
        ],
        "identity_only_right": [
            identity_document(identity) for identity in right_only
        ],
        "_left_stream": left_stream,
        "_right_stream": right_stream,
        "_left_index": left_index,
        "_right_index": right_index,
        "_common_identities": ordered_common,
    }


def member_multiset(row: Mapping[str, Any], field: str) -> tuple[str, ...]:
    value = row.get(field, ())
    if isinstance(value, str):
        members = tuple(item for item in value.split(";") if item)
    elif isinstance(value, Sequence):
        members = tuple(str(item) for item in value)
    else:
        raise ValueError("member multiset must be a sequence or semicolon list")
    return tuple(sorted(members))


def multiset_checksum(members: Sequence[str]) -> str:
    return hashlib.sha256(
        json.dumps(sorted(members), separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def compare_formal_members(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> dict[str, Any]:
    left_members = member_multiset(left, "formal_result_members")
    right_members = member_multiset(right, "formal_result_members")
    left_ordered = tuple(
        str(item) for item in left.get("formal_result_members", ())
    )
    right_ordered = tuple(
        str(item) for item in right.get("formal_result_members", ())
    )
    set_equal = Counter(left_members) == Counter(right_members)
    order_equal = left_ordered == right_ordered
    if not set_equal:
        classification = "STRICT_IDENTITY_FORMAL_MEMBER_SET_DIVERGED"
    elif not order_equal:
        classification = "FORMAL_RESULT_ORDER_DIVERGED_SET_EQUAL"
    else:
        classification = "FORMAL_RESULT_MEMBER_SET_AND_ORDER_EQUAL"
    return {
        "classification": classification,
        "formal_member_multiset_equal": set_equal,
        "formal_result_order_equal": order_equal,
        "left_formal_result_count": len(left_members),
        "right_formal_result_count": len(right_members),
        "left_formal_result_multiset_checksum": multiset_checksum(left_members),
        "right_formal_result_multiset_checksum": multiset_checksum(right_members),
        "left_formal_result_members": list(left_members),
        "right_formal_result_members": list(right_members),
        "missing_from_right": sorted(
            (Counter(left_members) - Counter(right_members)).elements()
        ),
        "unexpected_in_right": sorted(
            (Counter(right_members) - Counter(left_members)).elements()
        ),
    }


def check_previous_query_identity(
    *,
    alignment: Mapping[str, Any],
    current_identity: Sequence[Any],
    left_shadow_by_identity: Mapping[tuple[Any, ...], Sequence[str]],
    right_shadow_by_identity: Mapping[tuple[Any, ...], Sequence[str]],
    left_formal_by_identity: Mapping[tuple[Any, ...], Sequence[str]],
    right_formal_by_identity: Mapping[tuple[Any, ...], Sequence[str]],
    left_token_status_by_identity: Mapping[tuple[Any, ...], str],
    right_token_status_by_identity: Mapping[tuple[Any, ...], str],
    left_token_signature_by_identity: Mapping[tuple[Any, ...], str | None],
    right_token_signature_by_identity: Mapping[tuple[Any, ...], str | None],
) -> dict[str, Any]:
    """Apply the frozen previous-query identity rule to one witness."""
    identity = tuple(current_identity)
    left_stream = list(alignment["_left_stream"])
    right_stream = list(alignment["_right_stream"])
    if identity not in left_stream or identity not in right_stream:
        return {
            "PREVIOUS_QUERY_IDENTITY_PASS": False,
            "classification": "NO_STRICT_QUERY_IDENTITY_OVERLAP",
            "previous_identity": None,
        }
    left_position = left_stream.index(identity)
    right_position = right_stream.index(identity)
    prefix_equal = (
        left_position == right_position
        and left_stream[:left_position] == right_stream[:right_position]
    )
    if not prefix_equal:
        return {
            "PREVIOUS_QUERY_IDENTITY_PASS": False,
            "classification": "QUERY_STREAM_DIVERGED_BEFORE_RESULT_WITNESS",
            "previous_identity": None,
        }
    if left_position == 0:
        return {
            "PREVIOUS_QUERY_IDENTITY_PASS": True,
            "classification": "NO_PREVIOUS_QUERY_CURRENT_IS_STREAM_START",
            "previous_identity": None,
        }
    previous = left_stream[left_position - 1]
    status_left = left_token_status_by_identity.get(previous)
    status_right = right_token_status_by_identity.get(previous)
    comparable = status_left in {
        "CAPTURED_NONEMPTY", "CAPTURED_EMPTY_FORMAL_QUERY"
    } and status_right in {
        "CAPTURED_NONEMPTY", "CAPTURED_EMPTY_FORMAL_QUERY"
    }
    shadow_equal = Counter(left_shadow_by_identity.get(previous, ())) == Counter(
        right_shadow_by_identity.get(previous, ())
    )
    formal_equal = Counter(left_formal_by_identity.get(previous, ())) == Counter(
        right_formal_by_identity.get(previous, ())
    )
    token_equal = (
        comparable
        and left_token_signature_by_identity.get(previous)
        == right_token_signature_by_identity.get(previous)
    )
    passed = shadow_equal and formal_equal and comparable
    classification = (
        "PREVIOUS_QUERY_IDENTITY_MATCHED"
        if passed and token_equal else
        "TREE_SHAPE_DIFFERED_BUT_RESULT_COMPLETE"
        if passed else
        "PREVIOUS_QUERY_IDENTITY_EVIDENCE_GAP"
    )
    return {
        "PREVIOUS_QUERY_IDENTITY_PASS": passed,
        "classification": classification,
        "previous_identity": identity_document(previous),
        "previous_shadow_state_equal": shadow_equal,
        "previous_formal_member_set_equal": formal_equal,
        "previous_token_status_comparable": comparable,
        "previous_token_sequence_equal": token_equal if comparable else None,
    }


def public_alignment(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: item for key, item in value.items() if not key.startswith("_")
    }


__all__ = [
    "IDENTITY_FIELDS",
    "STRICT_QUERY_IDENTITY_SCHEMA_VERSION",
    "align_strict_query_streams",
    "check_previous_query_identity",
    "compare_formal_members",
    "identity_document",
    "identity_key",
    "identity_sha256",
    "member_multiset",
    "multiset_checksum",
    "public_alignment",
    "strict_query_identity",
]
