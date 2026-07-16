import csv
import json
import shutil
from pathlib import Path

import pytest

from eval.stage2_failure_day11b_provenance import result_tree_manifest
from eval.stage2_failure_day12_input_audit import verify_day11b_v2_plot_input

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2"


def test_frozen_v2_input_passes_full_recalculation():
    audit = verify_day11b_v2_plot_input(ROOT, RUN)
    assert audit["DAY12_INPUT_AUDIT_PASS"] is True
    assert audit["actual_case_count"] == 8
    assert audit["actual_merged_row_count"] == 312


def test_v1_is_rejected_as_plot_input():
    v1 = RUN.parent / "stage2_failure_day11b_replay_v1"
    audit = verify_day11b_v2_plot_input(ROOT, v1)
    assert audit["DAY12_INPUT_AUDIT_PASS"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    (("DAY11B_V2_RUNTIME_RESULT", "FAIL"), ("DAY11B_V2_PROVENANCE_COMPLETE", False)),
)
def test_manifest_gate_mutation_is_rejected(tmp_path, field, value):
    copied = tmp_path / RUN.name
    shutil.copytree(RUN, copied)
    frozen = tmp_path / "tree.txt"
    frozen.write_bytes(result_tree_manifest(tmp_path, copied))
    manifest_path = copied / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest[field] = value
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    audit = verify_day11b_v2_plot_input(tmp_path, copied, frozen)
    assert audit["DAY12_INPUT_AUDIT_PASS"] is False


@pytest.mark.parametrize(
    ("relative_path", "suffix"),
    (("run_manifest.json", "\n"), ("replay_frame_diagnostics_merged.csv", "\n")),
)
def test_frozen_tree_rejects_manifest_or_merged_byte_change(tmp_path, relative_path, suffix):
    copied = tmp_path / RUN.name
    shutil.copytree(RUN, copied)
    frozen = tmp_path / "tree.txt"
    frozen.write_bytes(result_tree_manifest(tmp_path, copied))
    target = copied / relative_path
    target.write_text(target.read_text(encoding="utf-8") + suffix, encoding="utf-8")
    assert verify_day11b_v2_plot_input(tmp_path, copied, frozen)["DAY12_INPUT_AUDIT_PASS"] is False


def test_missing_required_file_stops_audit(tmp_path):
    copied = tmp_path / RUN.name
    shutil.copytree(RUN, copied)
    (copied / "replay_plan.csv").unlink()
    audit = verify_day11b_v2_plot_input(ROOT, copied, tmp_path / "missing")
    assert audit["DAY12_INPUT_AUDIT_PASS"] is False
    assert "replay_plan.csv" in audit["missing_files"]


def test_replay_plan_with_missing_case_is_rejected(tmp_path):
    copied = tmp_path / RUN.name
    shutil.copytree(RUN, copied)
    plan = copied / "replay_plan.csv"
    with plan.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields, rows = list(reader.fieldnames or ()), list(reader)
    with plan.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows[:-1])
    frozen = tmp_path / "tree.txt"
    frozen.write_bytes(result_tree_manifest(tmp_path, copied))
    assert verify_day11b_v2_plot_input(tmp_path, copied, frozen)["DAY12_INPUT_AUDIT_PASS"] is False


def test_axial_summary_or_equivalence_failure_is_rejected(tmp_path):
    for filename, field in (
        ("axial_support_summary.json", "axial_only_audit_pass"),
    ):
        copied = tmp_path / filename.replace(".json", "") / RUN.name
        shutil.copytree(RUN, copied)
        path = copied / filename
        value = json.loads(path.read_text())
        value[field] = False
        path.write_text(json.dumps(value), encoding="utf-8")
        frozen = copied.parent / "tree.txt"
        frozen.write_bytes(result_tree_manifest(copied.parent, copied))
        assert verify_day11b_v2_plot_input(copied.parent, copied, frozen)["DAY12_INPUT_AUDIT_PASS"] is False

    copied = tmp_path / "equivalence" / RUN.name
    shutil.copytree(RUN, copied)
    path = copied / "v1_v2_scientific_equivalence_audit.csv"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace(",True\n", ",False\n", 1), encoding="utf-8")
    frozen = copied.parent / "tree.txt"
    frozen.write_bytes(result_tree_manifest(copied.parent, copied))
    assert verify_day11b_v2_plot_input(copied.parent, copied, frozen)["DAY12_INPUT_AUDIT_PASS"] is False


@pytest.mark.parametrize(
    "field",
    ("points_lidar_base_checksum", "normals_world_base_checksum", "R_diag_list_checksum"),
)
def test_base_observation_checksum_mismatch_is_rejected(tmp_path, field):
    copied = tmp_path / RUN.name
    shutil.copytree(RUN, copied)
    case_manifest = next((copied / "cases").glob("*/case_manifest.json"))
    value = json.loads(case_manifest.read_text())
    value[field] = "0" * 64
    case_manifest.write_text(json.dumps(value), encoding="utf-8")
    frozen = tmp_path / "tree.txt"
    frozen.write_bytes(result_tree_manifest(tmp_path, copied))
    audit = verify_day11b_v2_plot_input(tmp_path, copied, frozen)
    assert audit["DAY12_INPUT_AUDIT_PASS"] is False


def test_non_axial_contamination_is_rejected(tmp_path):
    copied = tmp_path / RUN.name
    shutil.copytree(RUN, copied)
    merged = copied / "replay_frame_diagnostics_merged.csv"
    with merged.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields, rows = list(reader.fieldnames or ()), list(reader)
    target = next(row for row in rows if row["stress"] == "coherent_subhuber_slip" and row["stress_active"] == "True")
    target["contaminated_non_axial_support_count"] = "1"
    with merged.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    frozen = tmp_path / "tree.txt"
    frozen.write_bytes(result_tree_manifest(tmp_path, copied))
    assert verify_day11b_v2_plot_input(tmp_path, copied, frozen)["DAY12_INPUT_AUDIT_PASS"] is False
