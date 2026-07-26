from pathlib import Path

from capture_range.day2_development_pipeline import REQUIRED_OUTPUT_FILES, TRIAL_FIELDS
from capture_range.day2_development_protocol import load_day2_development_protocol

ROOT = Path(__file__).resolve().parents[1]


def test_development_execution_matrix_and_output_contract():
    protocol = load_day2_development_protocol(ROOT)
    assert protocol.section("registration")["expected_trial_rows"] == 120960
    assert protocol.section("snapshot_contract")["expected_base_snapshot_count"] == 210
    assert tuple(REQUIRED_OUTPUT_FILES) == tuple(protocol.section("outputs")["exact_required_files"])
    assert "correspondence_checksum_change_count" in TRIAL_FIELDS
    assert "base_snapshot_checksum" in TRIAL_FIELDS
    assert "day2_test_lock.json" not in REQUIRED_OUTPUT_FILES
