from phase_a_execution_chain_test_support import sample_result
from zero_perturbation.phase_a_trial_result_schema import canonical_json_bytes
from zero_perturbation.phase_a_trial_result_writer import write_phase_a_trial_result


def test_writer_uses_sorted_utf8_json_with_trailing_newline(tmp_path):
    value = sample_result()
    path, _ = write_phase_a_trial_result(tmp_path, value)
    assert path.read_bytes() == canonical_json_bytes(value)
    assert path.read_bytes().endswith(b"\n")
