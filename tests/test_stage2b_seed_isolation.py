import pytest

from eval.weak_update_stage2b_lock import validate_seed_isolation


def test_development_and_test_seed_namespaces_are_disjoint():
    development = {"geometry_seeds": [1], "sensor_seeds": [2], "process_seeds": [3]}
    test = {"geometry_seeds": [4], "sensor_seeds": [5], "process_seeds": [6]}
    validate_seed_isolation(development, test)
    test["process_seeds"] = [3]
    with pytest.raises(RuntimeError, match="process_seeds overlap"):
        validate_seed_isolation(development, test)

