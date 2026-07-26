import csv

import pytest

from fastlio2_adapter.day7_map_update_events import (
    load_events,
    mutation_event_checksum,
)


def event_row(**updates):
    row = {
        "schema_version": "Day7MapMutationEventV1",
        "run_id": "multihyp_day7_map_update_r1",
        "event_sequence": 1,
        "scan_index": 150,
        "call_index": 0,
        "batch_id": "150:0",
        "batch_kind": "DOWNSAMPLED",
        "batch_point_index": 0,
        "event_index_within_call": 0,
        "operation_type": 1,
        "formal_callsite": "KD_TREE::Add_Points",
        "candidate_point_sha256": "11" * 32,
        "voxel_identity": "00000000" * 6,
        "existing_representative_sha256": "",
        "selected_representative_sha256": "11" * 32,
        "downsample_enabled": 1,
        "decision_context_member_count": 0,
        "decision_context_ordered_checksum": 14695981039346656037,
        "decision_context_multiset_checksum": 14695981039346656037,
        "formal_outcome": "INSERTED_NEW_VOXEL_REPRESENTATIVE",
        "mutation_destination": "DIRECT_TREE",
        "rebuild_active_at_decision": 0,
        "rebuild_generation": 2,
        "logical_mutation_epoch": 4,
        "logical_point_count_delta_claimed": 1,
        "logger_entry_sequence": 0,
        "event_schema_pass": 1,
        "diagnostic_internal_error": 0,
        "event_checksum": 0,
    }
    row.update(updates)
    row["event_checksum"] = mutation_event_checksum(row)
    return row


def write_event(path, row):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=row)
        writer.writeheader()
        writer.writerow(row)


def test_valid_event_schema_and_checksum(tmp_path):
    path = tmp_path / "events.csv"
    write_event(path, event_row())
    assert load_events(path)[0]["formal_outcome"] == (
        "INSERTED_NEW_VOXEL_REPRESENTATIVE"
    )


def test_corrupt_event_checksum_fails_closed(tmp_path):
    path = tmp_path / "events.csv"
    row = event_row()
    row["event_checksum"] += 1
    write_event(path, row)
    with pytest.raises(ValueError, match="checksum"):
        load_events(path)


def test_unclassified_event_fails_closed(tmp_path):
    path = tmp_path / "events.csv"
    row = event_row(formal_outcome="UNCLASSIFIED_FORMAL_PATH")
    row["event_checksum"] = 0
    write_event(path, row)
    with pytest.raises(ValueError, match="unclassified"):
        load_events(path)
