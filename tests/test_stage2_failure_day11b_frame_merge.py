import pytest

from eval import stage2_failure_day11b_schema as schema
from eval.stage2_failure_day11b_stress_trace import STRESS_TRACE_FIELDS
from eval.stage2_failure_schema import FRAME_KEY_FIELDS, GT_FIELDS, ONLINE_FIELDS
from eval.stage2_failure_window_schema import WINDOW_FIELDS


def _rows():
    key = {
        "run_id": "run", "sequence_id": "seq", "sweep": "geometry", "level": "L4",
        "stress": "clean", "geometry_seed": 1, "sensor_seed": 2, "process_seed": 3,
        "method": "huber_full", "frame_index": 1, "timestamp": 0.1,
    }
    def make(fields, version):
        row = {field: 0.0 for field in fields}
        row.update(key)
        row["schema_version"] = version
        return row
    online = make(ONLINE_FIELDS, "online")
    gt = make(GT_FIELDS, "gt")
    window = make(WINDOW_FIELDS, "window")
    window["source_online_schema_version"] = "online"
    stress = make(STRESS_TRACE_FIELDS, "stress")
    return [online], [gt], [window], [stress]


def _disable_validators(monkeypatch):
    monkeypatch.setattr(schema, "validate_online_frame_record", lambda row: None)
    monkeypatch.setattr(schema, "validate_gt_frame_record", lambda row: None)
    monkeypatch.setattr(schema, "validate_window_record", lambda row: None)


def test_four_table_merge_is_one_to_one(monkeypatch):
    _disable_validators(monkeypatch)
    rows = _rows()
    merged = schema.merge_frame_records("case", *rows)
    assert len(merged) == 1
    assert set(merged[0]) == set(schema.MERGED_FIELDS)


def test_missing_frame_in_any_source_is_rejected(monkeypatch):
    _disable_validators(monkeypatch)
    online, gt, window, stress = _rows()
    with pytest.raises(ValueError, match="missing"):
        schema.merge_frame_records("case", online, gt, window, [])


def test_duplicate_frame_key_is_rejected(monkeypatch):
    _disable_validators(monkeypatch)
    online, gt, window, stress = _rows()
    with pytest.raises(ValueError, match="duplicate"):
        schema.merge_frame_records("case", online + online, gt, window, stress)
