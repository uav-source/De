import csv
from pathlib import Path

import numpy as np


SEQUENCES = [
    "OC-L0-S01-M1",
    "ST-L3-S01-M1",
    "CT-L2-S01-M2",
    "RT-L4-S01-M1",
]

METRIC_NAMES = ["ODI", "condition_number", "lambda_min_clamped", "AIS"]
TARGET_NAMES = ["axis_drift_rate", "cross_drift_rate", "weak_drift_alignment", "high_axis_drift_flag"]


def prepare_minimal_day14_results(base: Path) -> Path:
    results = base / "results" / "day14"
    for dirname in ["raw", "metrics", "tables", "figures"]:
        (results / dirname).mkdir(parents=True, exist_ok=True)

    for seq_idx, sequence_id in enumerate(SEQUENCES):
        write_raw_odi(results / "raw" / f"{sequence_id}_odi.csv", seq_idx)
        write_metrics(results / "metrics" / f"{sequence_id}_metrics.csv", seq_idx)

    write_day08_summary(results / "tables" / "day08_metric_summary.csv")
    write_day10_tables(results / "tables")
    return results


def prepare_minimal_observations(base: Path) -> Path:
    data_root = base / "data" / "minibench"
    for seq_idx, sequence_id in enumerate(SEQUENCES):
        seq_dir = data_root / sequence_id
        seq_dir.mkdir(parents=True, exist_ok=True)
        np.savez(
            seq_dir / "observations.npz",
            timestamps=np.arange(8, dtype=float) * 0.1,
            packed_J=packed_jacobians(seq_idx),
            r_list=np.zeros((8, 6), dtype=float),
            R_diag_list=np.ones((8, 6), dtype=float),
            num_points_per_frame=np.full(8, 6, dtype=np.int32),
            axis_per_frame=axis_per_frame(seq_idx),
            pose_gt=np.zeros((8, 8), dtype=float),
        )
    return data_root


def write_raw_odi(path: Path, seq_idx: int) -> None:
    fieldnames = [
        "timestamp",
        "eig_1",
        "eig_2",
        "eig_3",
        "eig_4",
        "eig_5",
        "eig_6",
        "ODI",
        "AIS",
        "lambda_min_clamped",
        "condition_number",
        "weak_reliable",
        "axis_alignment",
    ]
    rows = []
    for frame in range(8):
        tunnel = seq_idx > 0
        odi = 0.2 + 0.05 * frame if not tunnel else 0.72 + 0.01 * seq_idx + 0.002 * frame
        rows.append(
            {
                "timestamp": 0.1 * frame,
                "eig_1": 10.0 + seq_idx,
                "eig_2": 7.0 + 0.2 * frame,
                "eig_3": 5.0,
                "eig_4": 3.0,
                "eig_5": 1.5,
                "eig_6": 0.8 if not tunnel else 0.02 + 0.001 * frame,
                "ODI": odi,
                "AIS": -2.0 + 0.1 * seq_idx,
                "lambda_min_clamped": 0.8 if not tunnel else 0.02 + 0.001 * frame,
                "condition_number": 20.0 if not tunnel else 600.0 + frame,
                "weak_reliable": 0 if not tunnel else 1,
                "axis_alignment": np.nan if not tunnel else 0.95,
            }
        )
    write_csv(path, fieldnames, rows)


def write_metrics(path: Path, seq_idx: int) -> None:
    fieldnames = [
        "start_idx",
        "end_idx",
        "path_length",
        "axis_error_start",
        "axis_error_end",
        "axis_drift_rate",
        "cross_drift_rate",
        "mean_ODI",
        "median_ODI",
        "mean_AIS",
        "median_lambda_min",
        "median_lambda_min_clamped",
        "median_condition_number",
        "weak_drift_alignment",
    ]
    rows = []
    for win, (start, end) in enumerate([(0, 2), (2, 4), (4, 7)]):
        tunnel = seq_idx > 0
        rows.append(
            {
                "start_idx": start,
                "end_idx": end,
                "path_length": 1.0 + win,
                "axis_error_start": 0.1 * win,
                "axis_error_end": 0.1 * win + (0.01 if not tunnel else 0.3 + 0.05 * seq_idx),
                "axis_drift_rate": 0.01 + 0.002 * win if not tunnel else 0.25 + 0.03 * seq_idx + 0.01 * win,
                "cross_drift_rate": 0.02 + 0.001 * win,
                "mean_ODI": 0.25 + 0.05 * win if not tunnel else 0.72 + 0.01 * seq_idx + 0.003 * win,
                "median_ODI": 0.25 + 0.05 * win if not tunnel else 0.72 + 0.01 * seq_idx + 0.003 * win,
                "mean_AIS": -2.0 + 0.1 * seq_idx,
                "median_lambda_min": 0.5 if not tunnel else 0.02,
                "median_lambda_min_clamped": 0.5 if not tunnel else 0.02,
                "median_condition_number": 20.0 if not tunnel else 600.0,
                "weak_drift_alignment": 0.1 if not tunnel else 0.9,
            }
        )
    write_csv(path, fieldnames, rows)


def write_day08_summary(path: Path) -> None:
    fieldnames = [
        "sequence_id",
        "ATE_RMSE",
        "RPE_mean",
        "final_axis_error",
        "final_cross_error",
        "mean_axis_error",
        "mean_cross_error",
        "axis_drift_rate_median",
        "cross_drift_rate_median",
        "ODI_mean",
        "ODI_median",
        "AIS_mean",
        "lambda_min_median",
        "condition_number_median",
    ]
    rows = []
    for seq_idx, sequence_id in enumerate(SEQUENCES):
        tunnel = seq_idx > 0
        rows.append(
            {
                "sequence_id": sequence_id,
                "ATE_RMSE": 0.01 if not tunnel else 1.0 + seq_idx,
                "RPE_mean": 0.01,
                "final_axis_error": 0.01 if not tunnel else 2.0 + seq_idx,
                "final_cross_error": 0.02,
                "mean_axis_error": 0.01 if not tunnel else 1.0 + seq_idx,
                "mean_cross_error": 0.02,
                "axis_drift_rate_median": 0.01 if not tunnel else 0.3,
                "cross_drift_rate_median": 0.02,
                "ODI_mean": 0.3 if not tunnel else 0.75,
                "ODI_median": 0.3 if not tunnel else 0.75,
                "AIS_mean": -2.0,
                "lambda_min_median": 0.5 if not tunnel else 0.02,
                "condition_number_median": 20.0 if not tunnel else 600.0,
            }
        )
    write_csv(path, fieldnames, rows)


def write_day10_tables(table_dir: Path) -> None:
    merged_fields = [
        "scope",
        "metric_name",
        "target_name",
        "spearman_rho",
        "spearman_p",
        "pearson_r",
        "bootstrap_ci_low",
        "bootstrap_ci_high",
        "auc_if_available",
        "valid_sample_count",
        "reason",
    ]
    per_fields = [
        "sequence_id",
        "metric_name",
        "target_name",
        "spearman_rho",
        "spearman_p",
        "pearson_r",
        "valid_sample_count",
        "reason",
    ]
    loso_fields = [
        "held_out_sequence",
        "metric_name",
        "target_name",
        "train_spearman_rho",
        "test_spearman_rho_or_auc",
        "valid_train_sample_count",
        "valid_test_sample_count",
        "reason",
    ]
    merged_rows = []
    per_rows = []
    loso_rows = []
    for metric_idx, metric in enumerate(METRIC_NAMES):
        for target_idx, target in enumerate(TARGET_NAMES):
            rho = 0.65 - 0.1 * metric_idx if target == "axis_drift_rate" else 0.2 - 0.05 * target_idx
            merged_rows.append(
                {
                    "scope": "merged_all_sequences",
                    "metric_name": metric,
                    "target_name": target,
                    "spearman_rho": rho,
                    "spearman_p": 0.01,
                    "pearson_r": rho,
                    "bootstrap_ci_low": rho - 0.1,
                    "bootstrap_ci_high": rho + 0.1,
                    "auc_if_available": np.nan,
                    "valid_sample_count": 12,
                    "reason": "",
                }
            )
            for seq_idx, sequence_id in enumerate(SEQUENCES):
                per_rows.append(
                    {
                        "sequence_id": sequence_id,
                        "metric_name": metric,
                        "target_name": target,
                        "spearman_rho": (-0.2 + 0.1 * seq_idx) if target == "axis_drift_rate" else 0.1,
                        "spearman_p": 0.5,
                        "pearson_r": 0.0,
                        "valid_sample_count": 3,
                        "reason": "",
                    }
                )
                loso_rows.append(
                    {
                        "held_out_sequence": sequence_id,
                        "metric_name": metric,
                        "target_name": target,
                        "train_spearman_rho": rho,
                        "test_spearman_rho_or_auc": (-0.2 + 0.1 * seq_idx) if target == "axis_drift_rate" else 0.1,
                        "valid_train_sample_count": 9,
                        "valid_test_sample_count": 3,
                        "reason": "",
                    }
                )
    write_csv(table_dir / "day10_metric_validity.csv", merged_fields, merged_rows)
    write_csv(table_dir / "day10_metric_validity_per_sequence.csv", per_fields, per_rows)
    write_csv(table_dir / "day10_metric_validity_loso.csv", loso_fields, loso_rows)


def packed_jacobians(seq_idx: int) -> np.ndarray:
    frames = []
    for frame in range(8):
        if seq_idx == 0:
            diag = np.asarray([1.0, 0.95 + 0.03 * frame, 0.9, 0.85, 0.8 + 0.02 * frame, 0.75], dtype=float)
        else:
            diag = np.asarray([1.0, 1.0 + 0.02 * frame, 1.0, 0.02 + 0.002 * frame, 1.0, 1.0], dtype=float)
        frames.append(np.diag(diag))
    return np.asarray(frames, dtype=float)


def axis_per_frame(seq_idx: int) -> np.ndarray:
    if seq_idx == 2:
        axis = np.asarray([0.8, 0.6, 0.0], dtype=float)
    else:
        axis = np.asarray([1.0, 0.0, 0.0], dtype=float)
    return np.tile(axis / np.linalg.norm(axis), (8, 1))


def write_csv(path: Path, fieldnames, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
