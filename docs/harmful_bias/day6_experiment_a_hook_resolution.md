# Day 6 Experiment A Hook Resolution

This table freezes the actual pre-instrumentation FAST-LIO2 hook locations used
for the restricted Experiment A replay pair. Line ranges are from the task
baseline; the final source-lock evidence records the post-instrumentation line
numbers. All accesses introduced by Experiment A are const/read-only snapshots
or checksums. No formal estimator, preprocessing, correspondence, or map-update
operation is replaced.

| stage | file | symbol | line_range | source_sha256 | formal_object | read_only_access | window_guard | confidence | notes |
|---|---|---|---:|---|---|---|---|---|---|
| raw LiDAR message callback | `src/laserMapping.cpp` | `livox_pcl_cbk` | 587-619 | `796ddeb709792a493fcbebbd91fb20a9a70f7aee9b5aef65cd83b36b9184f485` | incoming `livox_ros_driver::CustomMsg` before preprocessing | const message fields only | callback/scan index 135-160 | CONFIRMED | The fixed AVIA launch subscribes through the Livox callback, not `standard_pcl_cbk`. |
| raw IMU message callback | `src/laserMapping.cpp` | `imu_cbk` | 621-649 | `796ddeb709792a493fcbebbd91fb20a9a70f7aee9b5aef65cd83b36b9184f485` | incoming `sensor_msgs::Imu` | const message fields only | retained only when consumed by a guarded `MeasureGroup` | CONFIRMED | The bundle digest is not taken from the global buffer. |
| LiDAR/IMU synchronization | `src/laserMapping.cpp` | `sync_packages` | 653-709 | `796ddeb709792a493fcbebbd91fb20a9a70f7aee9b5aef65cd83b36b9184f485` | `MeasureGroup` assembly and LiDAR buffer front | sizes and timestamps only | runtime scan index 135-160 | CONFIRMED | Existing pop/order semantics are unchanged. |
| IMU bundle formation | `src/laserMapping.cpp` | `sync_packages` | 694-703 | `796ddeb709792a493fcbebbd91fb20a9a70f7aee9b5aef65cd83b36b9184f485` | ordered `Measures.imu` sequence | const sequence after formal assembly | runtime scan index 135-160 | CONFIRMED | Hashes the exact bundle consumed by `ImuProcess::Process`. |
| undistorted cloud complete | `src/laserMapping.cpp` | `main` loop after `p_imu->Process` | 1458-1476 | `796ddeb709792a493fcbebbd91fb20a9a70f7aee9b5aef65cd83b36b9184f485` | ordered `feats_undistort` | const point iteration only | runtime scan index 135-160 | CONFIRMED | The formal call resides in `src/IMU_Processing.hpp` (`Process`/`UndistortPcl`); that file is not modified. |
| before filter update | `src/laserMapping.cpp` | `main` loop | 1568-1573 | `796ddeb709792a493fcbebbd91fb20a9a70f7aee9b5aef65cd83b36b9184f485` | prior state/covariance and map-before-measurement | const state/covariance/map snapshots | runtime scan index 135-160 | CONFIRMED | Immediately precedes the unchanged `update_iterated_dyn_share_modified` call. |
| first valid linearization | `src/laserMapping.cpp` | `h_share_model` | 1005-1120 | `796ddeb709792a493fcbebbd91fb20a9a70f7aee9b5aef65cd83b36b9184f485` | existing accepted indices, correspondence/J/h/residual checksums | reuse existing in-call checksum result | active guarded scan, first valid call only | CONFIRMED | No new neighbor search or plane fitting is performed. |
| before map increment | `src/laserMapping.cpp` | `main` loop before `map_incremental` | 1587-1589 | `796ddeb709792a493fcbebbd91fb20a9a70f7aee9b5aef65cd83b36b9184f485` | post-update state/covariance and pre-insertion map | const snapshots only | runtime scan index 135-160 | CONFIRMED | Formal post-update state is read after the unchanged filter update. |
| insertion batches formed | `src/laserMapping.cpp` | `map_incremental` | 712-756 | `796ddeb709792a493fcbebbd91fb20a9a70f7aee9b5aef65cd83b36b9184f485` | ordered `PointToAdd` and `PointNoNeedDownsample` | const batch iteration before existing calls | active guarded scan only | CONFIRMED | Existing batch order and both `Add_Points` arguments remain unchanged. |
| map increment complete | `src/laserMapping.cpp` | `main` loop after `map_incremental` | 1589-1591 | `796ddeb709792a493fcbebbd91fb20a9a70f7aee9b5aef65cd83b36b9184f485` | post-insertion valid map snapshot | const traversal only | runtime scan index 135-160 | CONFIRMED | Snapshot exists only in memory and is reduced to counts and digests. |

The unchanged formal IMU/undistortion source baseline is
`src/IMU_Processing.hpp` SHA-256
`a456016e268680555919f58ae066354fd297a27f49be197292452f4147e1e0f5`.

`EXPERIMENT_A_HOOK_RESOLUTION_PASS=true`
