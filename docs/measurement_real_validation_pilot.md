# Measurement Real Validation Pilot

## Decision

The MUN-FRL Lighthouse single-sequence pilot passes its engineering and runtime
targets but fails its preregistered scientific gate:

```text
STAGE2_GATE = FAIL
TRANSITION = PIVOT
MEASUREMENT_REAL_PILOT_PASS = false
SECOND_DATASET_EXPANSION_AUTHORIZED = false
ODI_ADVANTAGE_ESTABLISHED = false
```

This is a detector measurement result, not a complete Degen-LIO result. No
FAST-LIO2 estimator path, Kalman state/covariance update, data association, map
update, residual weight, or iteration count was modified. No weak-direction
update, visual sensor, harmful-bias predictor, or further ikd-tree diagnosis
was added.

## Frozen input contract

The run uses only MUN-FRL Lighthouse:

- LiDAR: `/velodyne_points`, `sensor_msgs/PointCloud2`, frame `velodyne`, about
  10 Hz;
- IMU: `/imu/data`, `sensor_msgs/Imu`, frame `imu_link`, about 400 Hz;
- offline position reference: `/fix`, `sensor_msgs/NavSatFix`;
- bag SHA-256:
  `562bafc57dab7fdac3d8959cf6836b3f4508c4fa60147b11d718552180543162`.

The 22-byte little-endian point records were validated as `x/y/z/intensity`
float32 at offsets 0/4/8/12, `ring` uint16 at 16, and `time` float32 at 18.
Point time is used directly as scan-relative seconds; sampled values span
0--0.100604 s. Ring samples cover 0--15. IMU values use identity conversion in
rad/s and m/s². Message header time is mandatory: the maximum header-versus-bag
record offset is about 102,208,995 s, so the record epoch is not usable.

The frozen transform is applied only in this direction:

```text
p_imu = R_imu_lidar * p_lidar + t_imu_lidar
t = [-0.0593, 0.0468, -0.1249]
R = [0.0018, 0.0019, 1.0,
     0.0011, -1.0, 0.0019,
     1.0, 0.0011, -0.0018]
```

FAST-LIO2 uses Velodyne type 2, 16 scan lines, 10 Hz, timestamp-unit enum 0
(seconds), `time_sync_en=false`, and LiDAR-to-IMU offset 0.0034 s.

## Detector-independent interval and direction lock

The raw-scene inspection reads only the raw point cloud geometry and
position-only RTK trajectory; it does not import or evaluate detector code. The
interval configuration was committed at
`c4adddb16a60f29d799e56061495189155859730`, before formal detector execution,
with SHA-256
`c74d3af08054979c2cf0ecbb086a7b218a6541f691b82a1eb20706047086e4b4`.

- structural candidate: 1645814048.0--1645814062.0 s; detector-free raw XY
  scan-anisotropy median 130.43, range 45.32--331.66;
- geometry-rich control: 1645814164.0--1645814178.0 s; detector-free raw XY
  scan-anisotropy median 9.60, range 6.46--15.45.

The structural reference axis was frozen from the position-only RTK channel
centerline endpoints in ENU:
`[0.0661649, 0.8914754, 0.4482118]`, with conservative 15° angular uncertainty.
It was not generated from ODI, an information eigenvector, or a detector
output. Direction comparison uses `acos(abs(dot(...)))` to remove eigenvector
sign ambiguity.

## Read-only Measurement mode

The existing C++ compact exporter is used only as a transient transport for the
read-only Jacobian/residual observation. The Python Measurement processor calls
the frozen production `compute_metrics_for_frame` implementation and retains
only scalar frame metrics. The 97 MiB transient observation binary was deleted
after checksum/trailer verification, deterministic replay, and analysis.

The safety evidence is:

1. runtime tap same-call mutation count: 0;
2. Python processor state/covariance writes: 0;
3. detector feedback count: 0;
4. frozen-observation mismatch count: 0;
5. online reference access count: 0;
6. nonfinite detector output count: 0.

One scan changed the separate exporter-boundary aggregate estimator checksum.
For that scan the tap pre/post state, covariance, native/detector Jacobian,
innovation, geometric residual, correspondence, and map-size checksums all
match. It is reported as an export-boundary diagnostic and is not relabelled as
a tap same-call mutation.

## Position-only offline evaluation

The first valid GBAS/RTK fix is the WGS84-to-ENU origin. No reference
orientation is manufactured. FAST-LIO2 and ENU positions are aligned offline
with rigid SE(3) Kabsch alignment, no scale estimation. All 1719 FAST odometry
positions overlap the reference; none has bad RTK quality. Results are:

- position ATE RMSE: 0.35796 m;
- median position error: 0.31807 m;
- median local 5 s translation error: 0.12642 m;
- median future 5 s position-error growth: -0.00286 m.

The reference is never passed to the online detector and is not used to tune
ODI or any threshold.

## Engineering and runtime results

All 1722 lifecycle frames have valid compact records. There are 1719 valid
detector frames (99.826%); the three expected invalid reasons are first-scan
initialization, one empty undistorted scan, and local-map initialization. The
FAST-LIO2 crash count is zero. Python 3.11 full pytest reports 1286 passed, one
skipped, and 14 warnings.

Runtime is separated rather than combining disk logging with detector work:

| component | mean (ms) | q95 (ms) |
|---|---:|---:|
| capture core | 0.9601 | 2.1046 |
| detector core | 0.4926 | 0.5718 |
| logging/serialization | 0.6243 | 1.2172 |
| total added | 2.0769 | 3.8635 |

The detector-core mean is below 10 ms and total-added q95 is below 20 ms, so
both runtime targets pass.

## Scientific result

The frozen structural candidate has ODI median 0.6910, while the frozen
control has ODI median 0.8131. With the preregistered direction that higher ODI
means more degeneracy, ODI AUROC is 0.0020 and PR-AUC is 0.3087. ODI's Spearman
correlation with future 5 s position-error growth is -0.1730. It reaches neither
the AUROC 0.70 nor absolute-correlation 0.40 criterion.

The best traditional comparison is primary eigengap ratio at AUROC 0.3661 and
PR-AUC 0.4245. ODI-minus-best-traditional AUROC is -0.3642, so
`ODI_ADVANTAGE_NOT_ESTABLISHED` is required.

Structural weak-direction angle error has median 30.706°, q75 32.029°, and q95
34.259°, narrowly missing the fixed 30° criterion. Reliable frames have median
30.800° versus 28.980° for unreliable frames; reliability does not correspond
to lower observed angle error in this interval. The control interval triggers
on all 139 frames with a longest run of 139, so the frozen false-trigger
condition also fails.

Therefore the Scientific Pilot Gate fails. The project stops at this stage. No
second dataset is authorized, and the interval, metric formulas, threshold, and
reference axis remain unchanged after seeing the result.

## Reproduction

Validate and inspect before running the detector:

```bash
python3 scripts/130_validate_mun_frl_bag.py --bag "$MUN_FRL_BAG"
python3 scripts/129_inspect_mun_frl_intervals.py --bag "$MUN_FRL_BAG"
```

After verifying that the committed interval lock is unchanged:

```bash
scripts/131_run_mun_frl_measurement_pilot.sh --bag "$MUN_FRL_BAG"
python3.11 -m pytest -q
python3.11 scripts/132_analyze_mun_frl_measurement_pilot.py \
  --python311-pytest-pass
```

Generated data and full run products stay ignored. The compact, checksum-locked
result is in `artifacts/current/measurement_real_validation_pilot/`.
