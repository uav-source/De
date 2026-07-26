import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_three_new_python_processes_emit_identical_adapter_and_direct_bytes():
    code = """
from fastlio2_adapter.canonical_detector_output import canonical_json_line
from fastlio2_adapter.direct_production_diagnostic import evaluate_direct_production
from fastlio2_adapter.offline_detector_determinism import evaluate_frozen_observation
from test_adapter_precondition_domain import record_with_rows
import sys
record = record_with_rows(5)
adapter = canonical_json_line(evaluate_frozen_observation(record, record_index=284))
direct = canonical_json_line(evaluate_direct_production(record, record_index=284))
sys.stdout.buffer.write(adapter + direct)
"""
    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONHASHSEED": "0",
            "OMP_NUM_THREADS": "1",
            "OMP_DYNAMIC": "FALSE",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
            "LC_ALL": "C",
            "LANG": "C",
            "TZ": "UTC",
            "PYTHONPATH": os.pathsep.join(
                [str(ROOT / "src"), str(ROOT / "tests")]
            ),
        }
    )
    outputs = [
        subprocess.check_output([sys.executable, "-c", code], env=environment)
        for _ in range(3)
    ]
    assert outputs[0] == outputs[1] == outputs[2]


def test_remediation_runner_has_only_new_run_ids_and_two_streams():
    source = (ROOT / "scripts/72_run_fallback_c_remediation.py").read_text(
        encoding="utf-8"
    )
    assert "fresh_process_remediation_run_1" in source
    assert "fresh_process_run_1" not in source
    assert "adapter_detector_outputs_v3.jsonl" in source
    assert "direct_production_metrics_v1.jsonl" in source
    for forbidden in ("roscore", "roslaunch", "rosbag play"):
        assert forbidden not in source
