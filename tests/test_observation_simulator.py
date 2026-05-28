from pathlib import Path

import numpy as np

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from minibench.observation_simulator import (  # noqa: E402
    compute_point_to_plane_jacobian,
    frame_planes,
    information_matrix,
    load_detector_config,
    load_sequence,
    load_sequence_config,
    quat_to_rot,
    simulate_frame_observations,
    simulate_sequence_observations,
)


CONFIG = ROOT / "configs/detector/odi_default.yaml"


def seq(name):
    return ROOT / "data/minibench" / name


def ensure_generated_sequences():
    missing = [name for name in ["OC-L0-S01-M1", "ST-L3-S01-M1", "CT-L2-S01-M2", "RT-L4-S01-M1"] if not (seq(name) / "gt.tum").exists()]
    if missing:
        raise AssertionError(f"Day 4 generated sequence files are missing: {missing}")


def frame_observation(sequence_id, frame_idx=0):
    ensure_generated_sequences()
    sequence = load_sequence(seq(sequence_id))
    config = load_detector_config(CONFIG)
    pose = sequence.gt_poses[frame_idx]
    rng = np.random.default_rng(sequence.metadata["random_seed"])
    return simulate_frame_observations(
        pose,
        {
            "sequence": sequence,
            "frame_idx": frame_idx,
            "rng": rng,
            "points_per_frame": 64,
        },
        {"point_noise_std_m": 0.02, **config},
    )


def translation_info_for_sequence(sequence_id, frame_idx=0):
    obs = frame_observation(sequence_id, frame_idx)
    H = information_matrix(obs["J"], obs["R_diag"])
    return np.diag(H[3:6, 3:6]), H


def test_point_to_plane_jacobian_shape_and_translation_block():
    R = np.eye(3)
    p_lidar = np.array([1.0, 2.0, 3.0])
    normal = np.array([0.0, 1.0, 0.0])

    J = compute_point_to_plane_jacobian(R, p_lidar, normal)

    assert J.shape == (6,)
    assert np.allclose(J[3:6], normal)


def test_observation_arrays_have_expected_shapes_and_positive_R_diag():
    obs = frame_observation("ST-L3-S01-M1")

    assert obs["J"].shape == (64, 6)
    assert obs["residuals"].shape == (64,)
    assert obs["R_diag"].shape == (64,)
    assert np.all(obs["R_diag"] > 0)


def test_information_matrix_is_symmetric_psd():
    obs = frame_observation("OC-L0-S01-M1")
    H = information_matrix(obs["J"], obs["R_diag"])
    eigvals = np.linalg.eigvalsh(H)

    assert np.allclose(H, H.T, atol=1.0e-8)
    assert eigvals.min() > -1.0e-8


def test_straight_tunnel_translation_x_information_is_weak():
    diag, _ = translation_info_for_sequence("ST-L3-S01-M1")

    assert diag[0] < 1.0e-9
    assert diag[1] > 1000.0 * max(diag[0], 1.0e-12)
    assert diag[2] > 1000.0 * max(diag[0], 1.0e-12)


def test_repetitive_tunnel_translation_x_information_is_weak():
    diag, _ = translation_info_for_sequence("RT-L4-S01-M1")

    assert diag[0] < 1.0e-9
    assert diag[1] > 1000.0 * max(diag[0], 1.0e-12)
    assert diag[2] > 1000.0 * max(diag[0], 1.0e-12)


def test_open_control_translation_information_not_concentrated_single_axis():
    diag, _ = translation_info_for_sequence("OC-L0-S01-M1")
    ratio = diag.max() / diag.min()

    assert diag.min() > 0.0
    assert ratio < 2.0


def test_ct_local_planes_follow_axis_csv_not_fixed_global_x():
    sequence = load_sequence(seq("CT-L2-S01-M2"))
    start_idx = 0
    end_idx = sequence.gt_poses.shape[0] - 1

    start_planes = frame_planes(sequence, start_idx)
    end_planes = frame_planes(sequence, end_idx)
    start_side = start_planes[0].normal
    end_side = end_planes[0].normal
    start_axis = sequence.axis[start_idx]
    end_axis = sequence.axis[end_idx]

    assert abs(float(start_side @ start_axis)) < 1.0e-8
    assert abs(float(end_side @ end_axis)) < 1.0e-8
    assert abs(float(start_side @ end_side)) < 0.95
    assert abs(float(start_axis @ end_axis)) < 0.95
    assert not np.allclose(start_side, end_side)


def test_ct_translational_null_direction_tracks_local_axis():
    sequence = load_sequence(seq("CT-L2-S01-M2"))
    for frame_idx in [0, sequence.gt_poses.shape[0] - 1]:
        obs = frame_observation("CT-L2-S01-M2", frame_idx=frame_idx)
        H = information_matrix(obs["J"], obs["R_diag"])
        H_t = H[3:6, 3:6]
        eigvals, eigvecs = np.linalg.eigh(H_t)
        weak = eigvecs[:, np.argmin(eigvals)]
        axis = sequence.axis[frame_idx]
        alignment = abs(float(weak @ axis))
        assert alignment > 0.95


def test_sequence_observations_npz_contract_shapes():
    observations = simulate_sequence_observations(seq("ST-L3-S01-M1"), CONFIG)

    frames = observations["pose_gt"].shape[0]
    assert observations["packed_J"].shape[0] == frames
    assert observations["packed_J"].shape[2] == 6
    assert observations["r_list"].shape == observations["R_diag_list"].shape
    assert observations["num_points_per_frame"].shape == (frames,)
    assert observations["axis_per_frame"].shape == (frames, 3)
    assert observations["pose_gt"].shape[1] == 8


def test_load_sequence_config_falls_back_from_stale_absolute_path():
    metadata = {
        "sequence_id": "RT-L4-S01-M1",
        "config_path": "/definitely/not/this/machine/RT-L4-S01-M1.yaml",
    }

    config = load_sequence_config(metadata)

    assert config["sequence_id"] == "RT-L4-S01-M1"
    assert config["sensor_stub"]["point_noise_std_m"] == 0.025


def test_load_sequence_config_raises_when_no_candidate_exists():
    metadata = {
        "sequence_id": "MISSING-L9-S99-M9",
        "config_path": "/definitely/not/this/machine/missing.yaml",
    }

    try:
        load_sequence_config(metadata)
    except FileNotFoundError as exc:
        assert "MISSING-L9-S99-M9" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError for missing config")
