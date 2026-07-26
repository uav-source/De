"""Frozen score semantics for the Measurement pilot scientific audit.

The polarity in this module is derived from the formula and detector contracts,
never from the observed pilot labels.  It intentionally does not modify the
production detector or its frozen configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy.stats import kendalltau, pearsonr, rankdata, spearmanr

from eval.measurement_real_analysis import binary_ranking_metrics


POSITIVE_CLASS = "structural_degeneracy_candidate"
NEGATIVE_CLASS = "geometry_rich_control"
POSITIVE_CLASS_VALUE = 1
RANDOM_EQUIVALENCE_SEED = 20260726
RANDOM_EQUIVALENCE_COUNT = 10_000


@dataclass(frozen=True)
class MetricSemantic:
    metric_name: str
    raw_definition: str
    larger_means: str
    smaller_means: str
    risk_oriented_transform: str
    risk_sign: float | None
    source_file: str
    source_line: str
    contract_consistent: bool
    formal_degeneracy_score: bool = True


METRIC_SEMANTICS = (
    MetricSemantic(
        "ODI_trans",
        "1 - (exp(-sum(p_i log(p_i))) - 1) / 2 for the 3-D translation Schur spectrum",
        "more concentrated, lower-effective-rank spectrum",
        "more isotropic, higher-effective-rank spectrum",
        "risk_score = raw_score",
        1.0,
        "src/degen_detector/odi_tracker.py",
        "34-49, 92-126",
        True,
    ),
    MetricSemantic(
        "AIS_trans",
        "mean(log(lambda_i + epsilon)) of normalized translation information",
        "greater absolute translation information",
        "weaker absolute translation information",
        "risk_score = -raw_score",
        -1.0,
        "src/degen_detector/whitened_info.py",
        "56-59",
        True,
    ),
    MetricSemantic(
        "lambda_min_trans",
        "smallest eigenvalue of normalized translation Schur information",
        "stronger weakest translation direction",
        "weaker least-observed translation direction",
        "risk_score = -raw_score",
        -1.0,
        "src/degen_detector/whitened_info.py",
        "62-64",
        True,
    ),
    MetricSemantic(
        "condition_number_trans",
        "lambda_max / max(lambda_min, epsilon)",
        "more ill-conditioned/anisotropic spectrum",
        "more balanced spectrum",
        "risk_score = raw_score",
        1.0,
        "src/degen_detector/whitened_info.py",
        "49-53",
        True,
    ),
    MetricSemantic(
        "lambda_min_over_lambda_max",
        "lambda_min / lambda_max",
        "more balanced minimum-to-maximum information",
        "relatively weaker minimum-information direction",
        "risk_score = -raw_score",
        -1.0,
        "src/degen_detector/weak_direction.py",
        "35-52",
        True,
    ),
    MetricSemantic(
        "spectral_entropy_trans",
        "log(effective_rank_trans) = log(3 - 2*ODI_trans)",
        "higher effective spectral dimension",
        "more concentrated, lower-rank spectrum",
        "risk_score = -raw_score",
        -1.0,
        "src/fastlio2_adapter/measurement_mode.py",
        "232-251",
        True,
    ),
    MetricSemantic(
        "effective_rank_trans",
        "3 - 2*ODI_trans",
        "higher effective spectral dimension",
        "more concentrated, lower-rank spectrum",
        "risk_score = -raw_score",
        -1.0,
        "src/fastlio2_adapter/measurement_mode.py",
        "232-251",
        True,
    ),
    MetricSemantic(
        "primary_eigengap",
        "lambda_2 - lambda_1 for ascending translation eigenvalues",
        "more identifiable minimum-eigenvalue direction (scale dependent)",
        "less identifiable minimum-eigenvalue direction",
        "N/A for degeneration label; -raw is only a direction-unreliability diagnostic",
        None,
        "src/fastlio2_adapter/measurement_mode.py",
        "206-215, 264-269",
        True,
        False,
    ),
    MetricSemantic(
        "primary_eigengap_ratio",
        "(lambda_2 - lambda_1) / lambda_max",
        "more identifiable/stable minimum-eigenvalue direction",
        "less identifiable/unstable minimum-eigenvalue direction",
        "N/A for degeneration label; -raw is only a direction-unreliability diagnostic",
        None,
        "src/degen_detector/weak_direction.py",
        "35-52",
        False,
        False,
    ),
)


def semantic_by_name() -> dict[str, MetricSemantic]:
    return {item.metric_name: item for item in METRIC_SEMANTICS}


def positive_class_value(label: str) -> int:
    if label == POSITIVE_CLASS:
        return POSITIVE_CLASS_VALUE
    if label == NEGATIVE_CLASS:
        return 0
    raise ValueError(f"label is outside the frozen binary contract: {label}")


def orient_risk_score(metric_name: str, values: Sequence[float]) -> np.ndarray:
    semantic = semantic_by_name()[metric_name]
    if semantic.risk_sign is None:
        raise ValueError(f"{metric_name} has no formal degeneration-risk polarity")
    return float(semantic.risk_sign) * np.asarray(values, dtype=np.float64)


def metric_contract_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in METRIC_SEMANTICS:
        rows.append(
            {
                "metric_name": item.metric_name,
                "raw_definition": item.raw_definition,
                "larger_means": item.larger_means,
                "smaller_means": item.smaller_means,
                "risk_oriented_transform": item.risk_oriented_transform,
                "source_file": item.source_file,
                "source_line": item.source_line,
                "contract_consistent": item.contract_consistent,
                "formal_degeneracy_score": item.formal_degeneracy_score,
            }
        )
    return rows


def auc_direction_rows(frame_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        row
        for row in frame_rows
        if str(row.get("detector_valid")) == "True"
        and row.get("interval_label") in {POSITIVE_CLASS, NEGATIVE_CLASS}
    ]
    labels = [positive_class_value(str(row["interval_label"])) for row in selected]
    output: list[dict[str, Any]] = []
    for item in METRIC_SEMANTICS:
        values = np.asarray([float(row[item.metric_name]) for row in selected])
        raw = binary_ranking_metrics(labels, values)
        reversed_result = binary_ranking_metrics(labels, -values)
        if item.risk_sign is None:
            semantic_auc = float("nan")
            semantic_ap = float("nan")
            semantic_status = "NOT_A_FORMAL_DEGENERATION_RISK_SCORE"
        else:
            semantic_result = binary_ranking_metrics(
                labels, item.risk_sign * values
            )
            semantic_auc = semantic_result["auroc"]
            semantic_ap = semantic_result["pr_auc_average_precision"]
            semantic_status = "FORMAL_SEMANTIC_POLARITY"
        output.append(
            {
                "metric_name": item.metric_name,
                "positive_class": POSITIVE_CLASS,
                "positive_class_value": POSITIVE_CLASS_VALUE,
                "negative_class": NEGATIVE_CLASS,
                "count": len(selected),
                "positive_count": int(np.sum(np.asarray(labels) == 1)),
                "negative_count": int(np.sum(np.asarray(labels) == 0)),
                "risk_oriented_transform": item.risk_oriented_transform,
                "semantic_status": semantic_status,
                "AUC_raw": raw["auroc"],
                "AUC_semantically_oriented": semantic_auc,
                "AUC_reversed_diagnostic": reversed_result["auroc"],
                "PR_AUC_semantically_oriented": semantic_ap,
                "reversed_is_formal_result": False,
            }
        )
    return output


def odi_export_relationship(odi: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(odi, dtype=np.float64)
    effective_rank = 3.0 - 2.0 * values
    if np.any(effective_rank <= 0.0):
        raise ValueError("ODI values are outside the 3-D effective-rank domain")
    return effective_rank, np.log(effective_rank)


def _correlation_rows(
    source: str,
    odi: np.ndarray,
    spectral_entropy: np.ndarray,
    effective_rank: np.ndarray,
    normalized_entropy: np.ndarray | None,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for name, raw in (
        ("spectral_entropy_trans", spectral_entropy),
        ("effective_rank_trans", effective_rank),
        ("normalized_eigenvalue_entropy_unregularized", normalized_entropy),
    ):
        if raw is None:
            continue
        raw = np.asarray(raw, dtype=np.float64)
        risk = -raw
        odi_ranks = rankdata(odi, method="average")
        risk_ranks = rankdata(risk, method="average")
        order = np.argsort(odi, kind="stable")
        ordered_risk = risk[order]
        tolerance = 1.0e-12
        violations = int(np.sum(np.diff(ordered_risk) < -tolerance))
        expected_rank, expected_entropy = odi_export_relationship(odi)
        if name == "effective_rank_trans":
            relation = "effective_rank = 3 - 2*ODI"
            residual = np.max(np.abs(raw - expected_rank))
        elif name == "spectral_entropy_trans":
            relation = "spectral_entropy = log(3 - 2*ODI)"
            residual = np.max(np.abs(raw - expected_entropy))
        else:
            relation = "diagnostic entropy from stored unregularized lambda/sum"
            residual = np.max(np.abs(raw - expected_entropy))
        output.append(
            {
                "source": source,
                "comparison": name,
                "count": int(odi.size),
                "pearson_raw": float(pearsonr(odi, raw).statistic),
                "spearman_raw": float(spearmanr(odi, raw).statistic),
                "kendall_tau_raw": float(kendalltau(odi, raw).statistic),
                "risk_rank_equality_ratio": float(np.mean(odi_ranks == risk_ranks)),
                "odi_unique_rank_count": int(np.unique(odi_ranks).size),
                "comparison_unique_rank_count": int(np.unique(risk_ranks).size),
                "monotonic_order_violation_count": violations,
                "analytic_relation": relation,
                "analytic_relation_max_abs_residual": float(residual),
            }
        )
    return output


def odi_equivalence_rows(
    valid_frame_rows: Iterable[Mapping[str, Any]],
    *,
    random_seed: int = RANDOM_EQUIVALENCE_SEED,
    random_count: int = RANDOM_EQUIVALENCE_COUNT,
) -> list[dict[str, Any]]:
    frames = [row for row in valid_frame_rows if str(row.get("detector_valid")) == "True"]
    odi = np.asarray([float(row["ODI_trans"]) for row in frames])
    entropy = np.asarray([float(row["spectral_entropy_trans"]) for row in frames])
    effective_rank = np.asarray([float(row["effective_rank_trans"]) for row in frames])
    probabilities = np.asarray(
        [
            [
                float(row["normalized_eigenvalue_min"]),
                float(row["normalized_eigenvalue_mid"]),
                float(row["normalized_eigenvalue_max"]),
            ]
            for row in frames
        ]
    )
    unregularized_entropy = -np.sum(
        np.where(probabilities > 0.0, probabilities * np.log(probabilities), 0.0),
        axis=1,
    )
    output = _correlation_rows(
        "all_detector_valid_real_frames",
        odi,
        entropy,
        effective_rank,
        unregularized_entropy,
    )

    rng = np.random.default_rng(random_seed)
    eig = np.exp(rng.uniform(-12.0, 12.0, size=(random_count, 3)))
    epsilon = np.maximum(np.mean(eig, axis=1) * 1.0e-6, 1.0e-6)
    weights = eig + epsilon[:, None]
    probabilities_random = weights / np.sum(weights, axis=1, keepdims=True)
    entropy_random = -np.sum(probabilities_random * np.log(probabilities_random), axis=1)
    rank_random = np.exp(entropy_random)
    odi_random = 1.0 - (rank_random - 1.0) / 2.0
    output.extend(
        _correlation_rows(
            f"random_positive_eigenvalue_triples_seed_{random_seed}",
            odi_random,
            entropy_random,
            rank_random,
            None,
        )
    )
    return output
