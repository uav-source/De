import json

import pytest

from phase_a_execution_chain_test_support import FIXTURE_LOCK, FIXTURE_PLAN, actual_execution_chain
from zero_perturbation.phase_a_stage1_analysis import analyze_phase_a_stage1_fixture


def test_analysis_refuses_a_raw_result_with_an_untracked_mutation(actual_execution_chain):
    output = actual_execution_chain["output"]
    manifest = json.loads((output / "raw_result_manifest.json").read_text())
    entry = next(iter(manifest["results"].values()))
    path = output / "raw_results" / entry["path"]
    original = path.read_bytes()
    try:
        path.write_bytes(original + b" ")
        with pytest.raises(ValueError):
            analyze_phase_a_stage1_fixture(run_dir=output, fixture_plan=FIXTURE_PLAN, fixture_lock=FIXTURE_LOCK)
    finally:
        path.write_bytes(original)
