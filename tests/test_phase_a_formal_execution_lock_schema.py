import json

from phase_a_formal_lock_test_support import ROOT, make_valid_formal_lock, validate_case
from zero_perturbation.phase_a_formal_execution_lock_schema import (
    IMPLEMENTATION_BINDING_FIELDS,
    TOP_LEVEL_FIELDS,
)


def test_formal_execution_lock_schema_has_exact_required_fields(tmp_path):
    schema = json.loads((ROOT / "schemas/phase_a_formal_execution_lock_v1.schema.json").read_text())
    assert set(schema["required"]) == TOP_LEVEL_FIELDS
    assert schema["additionalProperties"] is False
    assert len(schema["required"]) == 20
    assert set(schema["properties"]["implementation_bindings"]["required"]) == IMPLEMENTATION_BINDING_FIELDS
    case = make_valid_formal_lock(tmp_path)
    assert validate_case(case)["validation"]["FORMAL_LOCK_SCHEMA_PASS"] is True
