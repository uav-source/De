import numpy as np


def test_geometry_measurement_ids_are_strictly_nested(nested_geometry_outputs):
    outputs = nested_geometry_outputs
    for frame in range(outputs["L1"]["measurement_ids"].shape[0]):
        sets = {
            level: set(np.asarray(outputs[level]["measurement_ids"][frame], dtype=np.int64).tolist())
            for level in ["L1", "L2", "L3", "L4"]
        }
        assert sets["L4"] < sets["L3"] < sets["L2"] < sets["L1"]
