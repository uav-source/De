import inspect

from capture_range.randomness import canonical_trial_seed_payload, derive_trial_seed


ARGS = (
    "snapshot_1",
    "translation",
    "translation_x_positive",
    0.1,
    2,
    42,
)


def test_trial_seed_is_stable_for_identical_identity_tuple():
    assert derive_trial_seed(*ARGS) == derive_trial_seed(*ARGS)
    assert canonical_trial_seed_payload(*ARGS) == canonical_trial_seed_payload(*ARGS)


def test_each_frozen_seed_identity_component_changes_the_seed():
    baseline = derive_trial_seed(*ARGS)
    variants = [
        ("snapshot_2", *ARGS[1:]),
        (ARGS[0], "rotation", *ARGS[2:]),
        (*ARGS[:2], "translation_x_negative", *ARGS[3:]),
        (*ARGS[:3], 0.2, *ARGS[4:]),
        (*ARGS[:4], 3, ARGS[5]),
        (*ARGS[:5], 43),
    ]
    assert all(derive_trial_seed(*variant) != baseline for variant in variants)


def test_seed_api_has_no_registration_path_or_algorithm_name_input():
    parameters = inspect.signature(derive_trial_seed).parameters
    assert list(parameters) == [
        "snapshot_id",
        "perturbation_type",
        "direction_id",
        "signed_amplitude",
        "repeat_index",
        "global_seed",
    ]


def test_positive_and_negative_zero_use_explicit_direction_identity():
    positive = derive_trial_seed(
        "snapshot_1", "translation", "translation_x_positive", 0.0, 0, 42
    )
    negative = derive_trial_seed(
        "snapshot_1", "translation", "translation_x_negative", -0.0, 0, 42
    )
    assert positive != negative
