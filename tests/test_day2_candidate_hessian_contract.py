from pathlib import Path

from degen_detector.whitened_info import compute_translation_schur_info

from capture_range.day2_protocol import (
    load_effective_day2_protocol,
    production_translation_schur_callable,
)


ROOT = Path(__file__).resolve().parents[1]


def test_candidate_contract_resolves_to_the_existing_production_schur_callable():
    contract = load_effective_day2_protocol(ROOT).amendment[
        "candidate_search_hessian_resolution"
    ]

    assert contract["matrix_name"] == "translation_schur_information_matrix"
    assert contract["source"] == (
        "existing_production_detector_schur_matrix_at_reference_pose"
    )
    assert contract["must_reuse_existing_detector_function"] is True
    assert contract["reimplementation_for_candidate_search_forbidden"] is True
    assert production_translation_schur_callable() is compute_translation_schur_info
    assert compute_translation_schur_info.__module__ == "degen_detector.whitened_info"
    assert compute_translation_schur_info.__name__ == "compute_translation_schur_info"


def test_candidate_spectrum_and_negative_eigenvalue_rules_are_frozen():
    contract = load_effective_day2_protocol(ROOT).amendment[
        "candidate_search_hessian_resolution"
    ]

    assert contract["construction_contract"] == {
        "whitening": "inherit_existing_detector_contract",
        "robust_weights": "same_reference_weights_used_by_day2_registration_snapshot",
        "symmetrization": "0.5 * (H + H.T)",
        "rotation_block_regularization": "inherit_existing_detector_contract",
        "eigenvalues_order": "ascending",
        "tiny_negative_eigenvalue_clip_tolerance": 1.0e-10,
        "negative_below_tolerance": "engineering_failure",
    }
    assert contract["derived_metrics"] == {
        "lambda_min": "smallest_clipped_eigenvalue",
        "lambda_max": "largest_clipped_eigenvalue",
        "condition_number_formula": "lambda_max / max(lambda_min, 1e-12)",
        "normalized_eigenvalue_vector_formula": (
            "eigenvalues / max(sum(eigenvalues), 1e-12)"
        ),
    }
    assert contract["snapshot_scope"] == {
        "one_matrix_per_reference_snapshot_before_any_initial_pose_perturbation": True,
        "same_matrix_used_for_all_directions_of_snapshot": True,
    }


def test_candidate_pool_similarity_and_capture_thresholds_are_unchanged():
    contract = load_effective_day2_protocol(ROOT).amendment[
        "candidate_search_hessian_resolution"
    ]

    assert contract["candidate_pair_pool"] == {
        "split": "test_only",
        "perturbation_type": "translation",
        "same_canonical_direction_id": True,
        "require_both_d50_exact": True,
    }
    assert contract["similarity_thresholds"] == {
        "normalized_eigenvalue_cosine_similarity_min": 0.98,
        "absolute_log_condition_number_ratio_max": 0.15,
        "absolute_log_lambda_min_ratio_max": 0.15,
    }
    assert contract["capture_difference"] == {
        "formula": "abs(d50_a-d50_b)/max(min(d50_a,d50_b),1e-6)",
        "minimum": 0.30,
    }
