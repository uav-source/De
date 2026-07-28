from phase_a_formal_lock_test_support import make_valid_formal_lock, validate_case
from zero_perturbation.phase_a_formal_execution_lock_schema import IMPLEMENTATION_BINDING_FIELDS


def test_formal_lock_has_exactly_all_implementation_bindings(tmp_path):
    case = make_valid_formal_lock(tmp_path)
    assert set(case.value["implementation_bindings"]) == IMPLEMENTATION_BINDING_FIELDS
    assert len(case.value["implementation_bindings"]) == 14
    assert validate_case(case)["validation"]["FORMAL_LOCK_ALL_IMPLEMENTATION_BINDINGS_REQUIRED"] is True
