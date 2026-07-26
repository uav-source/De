"""Offline logical-voxel shadow replay for Day 8 diagnostics.

This module never participates in FAST-LIO2 decisions.  It consumes only
canonical point identities, formal voxel identities, and Day 7 mutation events.
"""

from __future__ import annotations

import csv
import json
import struct
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .day8_range_query import canonical_member_checksum


INSERT = "INSERTED_NEW_VOXEL_REPRESENTATIVE"
REPLACE = {
    "REPLACED_EXISTING_VOXEL_REPRESENTATIVE",
    "REINSERTED_EXISTING_VOXEL_REPRESENTATIVE",
}
REJECT = "REJECTED_EXISTING_REPRESENTATIVE_CLOSER"
NO_DOWNSAMPLE = "ADDED_WITHOUT_DOWNSAMPLING"
DELETE = "DELETED_BY_BOX"
NO_DELETE = "DELETE_BOX_NO_MATCH"


def initialize_shadow(
    pairs: Iterable[tuple[str, str]],
) -> dict[str, set[str]]:
    state: dict[str, set[str]] = defaultdict(set)
    point_voxel: dict[str, str] = {}
    for point, voxel in pairs:
        if point in point_voxel and point_voxel[point] != voxel:
            raise ValueError("point belongs to multiple formal voxels")
        point_voxel[point] = voxel
        state[voxel].add(point)
    return dict(state)


def flatten_shadow(state: Mapping[str, set[str]]) -> set[str]:
    return {point for members in state.values() for point in members}


def decode_voxel_bounds(identity: str) -> tuple[float, ...]:
    if len(identity) != 48:
        raise ValueError("formal voxel/box identity must contain six floats")
    words = [
        int(identity[offset:offset + 8], 16)
        for offset in range(0, 48, 8)
    ]
    return tuple(
        struct.unpack(">f", word.to_bytes(4, "big"))[0] for word in words
    )


def _delete_box_members(
    state: Mapping[str, set[str]], box_identity: str,
) -> set[str]:
    q = decode_voxel_bounds(box_identity)
    deleted: set[str] = set()
    for voxel, members in state.items():
        v = decode_voxel_bounds(voxel)
        contained = all(q[axis] <= v[axis] for axis in range(3)) and all(
            q[axis + 3] >= v[axis + 3] for axis in range(3)
        )
        intersects = all(
            q[axis + 3] > v[axis] and q[axis] < v[axis + 3]
            for axis in range(3)
        )
        if contained:
            deleted.update(members)
        elif intersects and members:
            raise ValueError(
                "delete box partially intersects an occupied formal voxel"
            )
    return deleted


def apply_mutation(
    state: dict[str, set[str]],
    event: Mapping[str, Any],
    point_voxel: Mapping[str, str],
) -> int:
    outcome = str(event["formal_outcome"])
    voxel = str(event.get("voxel_identity", ""))
    selected = str(event.get("selected_representative_sha256", ""))
    candidate = str(event.get("candidate_point_sha256", ""))
    before = len(flatten_shadow(state))
    replacement_member_count = 0
    if outcome == INSERT:
        if not voxel or not selected:
            raise ValueError("invalid new-voxel insertion event")
        state.setdefault(voxel, set()).add(selected)
    elif outcome in REPLACE:
        if not voxel or not selected or not state.get(voxel):
            raise ValueError("invalid voxel replacement event")
        replacement_member_count = len(state[voxel])
        state[voxel] = {selected}
    elif outcome == REJECT:
        if not voxel or not state.get(voxel):
            raise ValueError("rejection refers to absent logical voxel")
    elif outcome == NO_DOWNSAMPLE:
        resolved = point_voxel.get(candidate)
        if not candidate or resolved is None:
            raise ValueError("no-downsample candidate voxel is unresolved")
        state.setdefault(resolved, set()).add(candidate)
    elif outcome == DELETE:
        deleted = _delete_box_members(state, voxel)
        for point in deleted:
            resolved = point_voxel.get(point)
            if resolved is None or point not in state.get(resolved, set()):
                raise ValueError("delete event cannot be resolved in shadow state")
            state[resolved].remove(point)
            if not state[resolved]:
                del state[resolved]
    elif outcome == NO_DELETE:
        if _delete_box_members(state, voxel):
            raise ValueError("delete-no-match box contains shadow members")
    else:
        raise ValueError(f"unsupported Day 7 mutation outcome: {outcome}")
    after = len(flatten_shadow(state))
    claimed = int(event["logical_point_count_delta_claimed"])
    actual = after - before
    # Day 7's replacement event delta is representative-level accounting.
    # A coherent snapshot may contain more than one logical member in the
    # formal voxel immediately before delete-box + reinsert.  Existing event
    # fields uniquely adjudicate the full logical-map delta as 1-N while the
    # event's representative claim remains zero.  This is an offline rule
    # only; it neither changes nor supplements the runtime event stream.
    replacement_ambiguity_resolved = (
        outcome in REPLACE
        and replacement_member_count > 1
        and claimed == 0
        and actual == 1 - replacement_member_count
    )
    if actual != claimed and not replacement_ambiguity_resolved:
        raise ValueError("shadow mutation delta does not match formal claim")
    return actual


def compare_query_to_shadow(
    query: Mapping[str, Any],
    state: Mapping[str, set[str]],
    *,
    run_id: str,
    reference: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    shadow = sorted(state.get(str(query["voxel_identity"]), set()))
    formal = sorted(query.get(
        "formal_result_members",
        str(query.get("formal_result_point_sha256_list", "")).split(";")
        if query.get("formal_result_point_sha256_list") else (),
    ))
    missing = sorted(set(shadow) - set(formal))
    unexpected = sorted(set(formal) - set(shadow))
    input_equal = (
        reference is None
        or all(
            query.get(field) == reference.get(field)
            for field in (
                "candidate_point_sha256", "voxel_identity",
                "query_box_checksum",
            )
        )
    )
    return {
        "run_id": run_id,
        "scan_index": int(query["scan_index"]),
        "call_index": int(query["map_mutation_call_index"]),
        "batch_point_index": int(query["batch_point_index"]),
        "query_sequence": int(query["query_sequence"]),
        "candidate_point_sha256": query["candidate_point_sha256"],
        "voxel_identity": query["voxel_identity"],
        "shadow_member_count": len(shadow),
        "formal_result_count": len(formal),
        "shadow_member_hashes": ";".join(shadow),
        "formal_result_hashes": ";".join(formal),
        "shadow_member_multiset_checksum": canonical_member_checksum(shadow),
        "missing_from_formal_result": ";".join(missing),
        "unexpected_in_formal_result": ";".join(unexpected),
        "query_input_equal_to_reference": int(input_equal),
        "shadow_state_accounting_pass": 1,
        "formal_query_completeness_pass": int(not missing and not unexpected),
    }


def replay_scan(
    *,
    run_id: str,
    before_pairs: Sequence[tuple[str, str]],
    after_pairs: Sequence[tuple[str, str]],
    queries: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    known_pairs: Mapping[str, str],
    tolerate_accounting_failure: bool = False,
) -> list[dict[str, Any]]:
    state = initialize_shadow(before_pairs)
    rows: list[dict[str, Any]] = []
    event_by_position: dict[tuple[int, int], list[Mapping[str, Any]]] = defaultdict(list)
    for event in events:
        event_by_position[
            (int(event["call_index"]), int(event["batch_point_index"]))
        ].append(event)
    queries_by_position: dict[
        tuple[int, int], list[Mapping[str, Any]]
    ] = defaultdict(list)
    for query in queries:
        queries_by_position[
            (
                int(query["map_mutation_call_index"]),
                int(query["batch_point_index"]),
            )
        ].append(query)
    positions = sorted(set(event_by_position) | set(queries_by_position))
    delta_failure_count = 0
    for position in positions:
        for query in queries_by_position[position]:
            rows.append(compare_query_to_shadow(query, state, run_id=run_id))
        for event in sorted(
            event_by_position[position],
            key=lambda row: int(row["event_sequence"]),
        ):
            outcome = str(event["formal_outcome"])
            voxel = str(event.get("voxel_identity", ""))
            legacy_ambiguous_delta = (
                outcome in REPLACE
                and len(state.get(voxel, set())) > 1
                and int(event["logical_point_count_delta_claimed"]) == 0
            )
            try:
                apply_mutation(state, event, known_pairs)
                # Preserve the old diagnostic mode for source-audit
                # recalculation.  Focused remediation uses the strict,
                # adjudicated mode (the default) and therefore records zero.
                if tolerate_accounting_failure and legacy_ambiguous_delta:
                    delta_failure_count += 1
            except ValueError as error:
                if (
                    tolerate_accounting_failure
                    and str(error)
                    == "shadow mutation delta does not match formal claim"
                ):
                    delta_failure_count += 1
                else:
                    raise
    actual = flatten_shadow(state)
    expected = {point for point, _ in after_pairs}
    closure_failure_count = int(actual != expected)
    if closure_failure_count and not tolerate_accounting_failure:
        raise ValueError(
            "shadow state does not close to coherent MAP_AFTER: "
            + json.dumps({
                "missing": sorted(expected - actual),
                "unexpected": sorted(actual - expected),
            }, sort_keys=True)
        )
    accounting_pass = int(
        delta_failure_count == 0 and closure_failure_count == 0
    )
    for row in rows:
        row.update({
            "shadow_mutation_delta_failure_count": delta_failure_count,
            "shadow_state_closure_failure_count": closure_failure_count,
            "shadow_state_accounting_pass": accounting_pass,
        })
    return rows


def replay_run(
    *,
    run_id: str,
    snapshots: Mapping[
        tuple[int, str], Sequence[tuple[str, str]]
    ],
    queries: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    tolerate_accounting_failure: bool = False,
) -> list[dict[str, Any]]:
    known_pairs: dict[str, str] = {}
    for values in snapshots.values():
        for point, voxel in values:
            prior = known_pairs.setdefault(point, voxel)
            if prior != voxel:
                raise ValueError("point-to-formal-voxel mapping changed")
    rows: list[dict[str, Any]] = []
    for scan in range(155, 166):
        rows.extend(replay_scan(
            run_id=run_id,
            before_pairs=snapshots[(scan, "MAP_BEFORE")],
            after_pairs=snapshots[(scan, "MAP_AFTER")],
            queries=[
                row for row in queries if int(row["scan_index"]) == scan
            ],
            events=[
                row for row in events if int(row["scan_index"]) == scan
            ],
            known_pairs=known_pairs,
            tolerate_accounting_failure=tolerate_accounting_failure,
        ))
    return rows


def write_comparison(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError("refusing empty shadow comparison")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
