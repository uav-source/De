# Stage 1 Day 7 — Day 8 Adapter Input Specification v1

This specification covers only the two samples with a READY release status. Day 7 did not implement either adapter and did not run FAST-LIO2.

## 1. MUN-FRL Lighthouse benchmarking bag — first target

- Input: indexed ROS1 bag v2.0.
- LiDAR: `/velodyne_points`, `sensor_msgs/PointCloud2`, frame `velodyne`, about 10 Hz.
- IMU: `/imu/data`, `sensor_msgs/Imu`, frame `imu_link`, effective average about 400 Hz.
- Reference: `/fix`, `sensor_msgs/NavSatFix`, raw RTK position only; no `/fix_ppk` or `/fix_frl` exists in this sample.
- Point layout: `x:float32@0`, `y:float32@4`, `z:float32@8`, `intensity:float32@12`, `ring:uint16@16`, `time:float32@18`; `point_step=22`, little-endian.
- Point time: scan-relative seconds. Conversion: `t_fastlio_seconds = float(point.time)`; do not multiply by 1e-3, 1e-6, or 1e-9.
- Ring: direct integer mapping, observed 0–15.
- IMU units: `rad/s` and `m/s^2`; conversion factors are 1.0. Use message headers, not bag-record epoch.
- Spatial extrinsic: LiDAR pose in IMU body, `p_imu = R_imu_lidar p_lidar + t_imu_lidar`; `t=[-0.0593, 0.0468, -0.1249] m`; row-major `R=[0.0018,0.0019,1; 0.0011,-1,0.0019; 1,0.0011,-0.0018]`. No inversion.
- Time setting: `time_sync_en=false`, `time_offset_lidar_to_imu=0.0034 s` from the official dataset-linked FAST-LIO configuration.
- Coordinate conversion: none inside the sensor adapter. A future reference parser may convert WGS84 to a documented local Cartesian frame, but must remain position-only.
- FAST-LIO2 configuration: Velodyne type, 16 lines, 10 Hz, timestamp unit seconds, native topics above, fixed extrinsic.
- New preprocessing: no algorithmic branch; only input validation for required fields and the message-header epoch.
- FAST-LIO2 core: do not change state propagation, map update, residuals, optimization, or Degen-LIO scientific logic.
- Minimal acceptance: fixture-level parsing of first/middle/last scans; exact time/ring assertions; SI IMU assertion; transform direction test; nondecreasing headers; no real-data formal localization.

## 2. NTU VIRAL eee_03 — second target

- Input: indexed ROS1 bag v2.0 extracted from the checksum-verified official ZIP.
- LiDAR: horizontal `/os1_cloud_node1/points`, frame `sensor1/os_sensor`, about 10 Hz. Do not combine the vertical stream in the first adapter.
- IMU: VN100 `/imu/imu`, frame `imu`, nominal 385 Hz. Do not substitute either Ouster internal six-axis IMU.
- Reference: `/leica/pose/relative`, `geometry_msgs/PoseStamped`, independent prism position at about 20 Hz; quaternion is a non-GT identity placeholder.
- Point layout: `x:float32@0`, `y:float32@4`, `z:float32@8`, `intensity:float32@16`, `t:uint32@20`, `reflectivity:uint16@24`, `ring:uint8@26`, `ambient:uint16@28`, `range:uint32@32`; `point_step=48`, 16x1024, little-endian.
- Point time: scan-relative nanoseconds. Conversion: `t_seconds = double(point.t) * 1e-9`, or configure the native FAST-LIO Ouster parser with `timestamp_unit=3`. Sampled range is approximately 0–100,030,550 ns.
- Ring: direct integer mapping, observed 0–15.
- IMU units: `rad/s` and `m/s^2`; conversion factors are 1.0.
- Spatial extrinsic: archive `T_Body_Lidar` maps horizontal LiDAR coordinates into Body; archive `T_Body_Imu=I`, so Body is the selected VN100 IMU frame. Use `R=I`, `t=[-0.050, 0, 0.055] m`; no inversion.
- Time handling: retain the official-site-linked `time_offset_lidar_to_imu=-0.1 s` as a configurable, tested value and apply the publisher's official Ouster/IMU regularization procedure. Do not silently repair or rewrite the source bag.
- Coordinate conversion: none for the horizontal LiDAR-to-body mapping. Reference evaluation must compensate `T_Body_Prism` translation `[-0.293656,-0.012288,-0.273095] m` using the estimate's orientation and remain position-only.
- FAST-LIO2 configuration: Ouster type, `scan_line=16`, timestamp unit nanoseconds, native topics, fixed archive extrinsic. Reject a rotation vector whose length is not 9.
- New preprocessing: a guarded NTU timing/field branch plus validation of 16 rings and nanosecond scan span. The actual archive—not the linked config's erroneous 32 lines/12 rotation values—is authoritative.
- FAST-LIO2 core: do not change propagation, optimization, map, residual, or scientific detection logic.
- Minimal acceptance: point layout/time/ring fixtures; VN100 selection and SI-unit test; 4x4 transform direction test; monotonic regularized-time test; explicit rejection of malformed calibration; no formal localization or trajectory metric run.

## Day 8 boundary

Allowed: implement small read-only parsers/preprocessors and configuration validation for these two contracts, add focused unit tests, and use tiny synthetic/fixture messages. Forbidden: FAST-LIO2 formal real-data localization, ODI real-data experiments, threshold tuning, ATE/RPE claims, core algorithm changes, patent edits, or work on a non-READY dataset.

DAY8_ADAPTER_INPUT_SPEC_COMPLETE: true
