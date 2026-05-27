# Day 1-14 Minibench Specification

This document freezes the four Day 14 minimum validation sequences and their
file contracts. Day 4 scene generation must follow this spec instead of
inventing new sequence names or output formats.

## Sequence Set

Only four sequences are in scope for Day 1-14:

| sequence_id | Role | Required scientific check |
| --- | --- | --- |
| `OC-L0-S01-M1` | Open control | ODI should remain low and weak direction should not be stable. |
| `ST-L3-S01-M1` | Straight tunnel | Translation along tunnel axis should be weakly constrained. |
| `CT-L2-S01-M2` | Curved tunnel | Weak translation direction should follow local centerline tangent. |
| `RT-L4-S01-M1` | Repetitive tunnel | Axis weakness plus repeated structure should produce high degeneracy. |

No additional sequences may be added before Day 14 unless a report explicitly
marks one of these four as invalid and explains the replacement.

## Sequence Naming

Sequence IDs use:

```text
<family>-<level>-<seed>-<motion>
```

Allowed Day 1-14 fields:

| Field | Meaning |
| --- | --- |
| `OC` | Open Control. |
| `ST` | Straight Tunnel. |
| `CT` | Curved Tunnel. |
| `RT` | Repetitive Tunnel. |
| `L0-L4` | Degeneracy difficulty level. |
| `S01` | Frozen deterministic seed group. |
| `M1/M2` | Motion profile ID. |

All configs must contain `random_seed: 42` for the Day 14 minimum probe. Future
multi-seed checks must be reported as a separate sensitivity experiment.

## Coordinate Convention

- World frame uses `x` forward, `y` left, `z` up.
- Straight tunnel axis is `[1, 0, 0]`.
- Curved tunnel axis is framewise local centerline tangent.
- All axis vectors saved to disk must be unit length.
- Positions are meters.
- Time is seconds.

## Required Output Directory

Each generated sequence must live at:

```text
data/minibench/<sequence_id>/
```

For example:

```text
data/minibench/ST-L3-S01-M1/
```

## Required Generated Files

Each sequence directory must contain the following files after Day 4-8 are
complete:

| File | Created by | Required content |
| --- | --- | --- |
| `gt.tum` | Day 4 scene generator | Ground truth pose in TUM format. |
| `axis.csv` | Day 4 scene generator | Per-frame unit axis or local tangent. |
| `planes.csv` | Day 4 scene generator | Plane normals and anchor points used by the simulator. |
| `scene_metadata.json` | Day 4 scene generator | Config hash, seed, scene family, difficulty, expected degeneracy. |
| `observations.npz` | Day 5 observation simulator | Timestamps, Jacobians, residuals, covariance diagonal, axes, GT poses. |
| `pose_init.tum` | Day 7 toy LIO | Initial or propagated pose before LiDAR correction, if available. |
| `pose_est_toy.tum` | Day 7 toy LIO | Estimated pose from the minimum synthetic LIO probe. |
| `metrics.csv` | Day 8 evaluator | ATE, RPE, axis/cross/weak drift metrics. |

If a future script cannot generate one of these files, it must fail loudly or
record the missing output in that day's report.

## File Schemas

### `gt.tum`

Whitespace-separated TUM pose format:

```text
timestamp tx ty tz qx qy qz qw
```

The number of rows must equal the sequence `frames` field.

### `axis.csv`

CSV columns:

```text
timestamp,axis_x,axis_y,axis_z,reliable
```

For straight sequences, every axis row should be close to `[1, 0, 0]`. For
curved sequences, each row stores the local centerline tangent.

### `planes.csv`

CSV columns:

```text
plane_id,frame_start,frame_end,nx,ny,nz,qx,qy,qz,semantic
```

For straight tunnel and repetitive tunnel, most structural plane normals must
have small `abs(nx)` so the tunnel axis is weakly constrained by point-to-plane
geometry.

### `scene_metadata.json`

Required fields:

```json
{
  "sequence_id": "...",
  "scene_family": "...",
  "difficulty": "...",
  "seed_id": "S01",
  "random_seed": 42,
  "config_path": "...",
  "config_sha256": "...",
  "expected_degeneracy": "...",
  "generated_by": "scripts/00_generate_minibench.py"
}
```

### `observations.npz`

Required arrays:

```text
timestamps
J_list or packed_J
r_list
R_diag_list
num_points_per_frame
axis_per_frame
pose_gt
```

`J_i` must follow the frozen 6DoF pose block:

```text
J_i = [n_i^T (-R [p_i]_x), n_i^T]
```

### `metrics.csv`

Required columns:

```text
sequence_id
timestamp
ATE
RPE
axis_error
cross_error
weak_error
axis_drift_rate
weak_drift_rate
ODI
AIS
lambda_min
condition_number
```

## Scientific Roles

### Open Control

Open control is a negative control. If it shows high ODI or a stable reliable
weak direction, the open scene or whitening scale is wrong.

### Straight Tunnel

Straight tunnel is the primary positive case. Wall, floor, and ceiling normals
should constrain lateral and vertical motion more than forward axis motion.

### Curved Tunnel

Curved tunnel checks whether weak direction is local, not a hard-coded global
`x` direction.

### Repetitive Tunnel

Repetitive tunnel keeps the straight tunnel axis weakness and adds repeated
features. Day 1-14 does not make a full data-association claim, but this
sequence should be the hardest minimum probe.

## Reproducibility Rules

- Every generated sequence must record `random_seed`.
- Every script must record its command in a report or manifest.
- Every output must be reproducible from the YAML config.
- No manual edits to generated CSV, NPZ, or figure files are allowed.
- Day 1-14 must not expand beyond these four sequences.

