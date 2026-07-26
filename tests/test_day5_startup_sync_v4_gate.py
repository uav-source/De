from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_finalizer():
    path = ROOT / "scripts/58_finalize_day5_startup_sync_v4.py"
    spec = importlib.util.spec_from_file_location("day5_v4_finalizer", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v4_constants_keep_runtime_equivalence_and_day6_out_of_scope() -> None:
    module = load_finalizer()
    assert module.RUN_ID == "multihyp_day5_startup_sync_v4"
    assert module.TOLERANCE == 1e-12
    assert module.REPEATS == (1, 2, 3)
    assert module.PAIRS == ((1, 2), (1, 3), (2, 3))


def test_selected_signature_covers_first_and_last_ten() -> None:
    module = load_finalizer()
    rows = [
        {
            "scan_index": index,
            "measure_group_checksum": index * 10,
            "timestamp_begin": float(index),
            "timestamp_end": float(index) + 0.1,
            "lidar_point_count": 100,
            "imu_message_count": 20,
        }
        for index in range(20)
    ]
    assert module.selected_signature(rows) != module.selected_signature(
        rows, tail=True
    )
    changed = [dict(row) for row in rows]
    changed[-1]["measure_group_checksum"] += 1
    assert module.selected_signature(rows) == module.selected_signature(changed)
    assert module.selected_signature(rows, tail=True) != module.selected_signature(
        changed, tail=True
    )


def test_run_directory_is_fixed_audit_only_layout(tmp_path: Path) -> None:
    module = load_finalizer()
    assert module.run_dir(tmp_path, "avia_quick_shack", 2) == (
        tmp_path
        / "runs/baseline/avia_quick_shack/AUDIT_ONLY_R2"
    )
