from phase_a_execution_chain_test_support import sample_result
from zero_perturbation.phase_a_trial_result_writer import write_phase_a_trial_result


def test_writer_leaves_only_complete_final_json(tmp_path):
    path, digest = write_phase_a_trial_result(tmp_path, sample_result())
    assert path.is_file() and len(digest) == 64
    assert not list(tmp_path.glob("*.tmp"))
