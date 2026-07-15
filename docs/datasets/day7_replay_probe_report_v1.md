# Stage 1 Day 7 Short Replay Probe Report v1

- Audit label date: 2026-07-26
- Execution environment date: 2026-07-15
- ROS environment: ROS Noetic `rosbag` v2 reader/player on Python 3.8.10
- Scope: two 8-second segments, each 4.41% or less of its source bag; only the selected LiDAR and IMU topics were published.
- Explicit exclusions: no FAST-LIO2 node, Degen-LIO detector, ODI calculation, trajectory alignment, ATE, or RPE was run; the source bags were not modified.

## Method

For each sample, a subscriber was registered before playback. Playback used `--clock --rate 2 --duration 8 --delay 1 --wait-for-subscribers` and was restricted to the primary LiDAR and IMU topics. MUN-FRL began 6 seconds into the bag because the workshop bag's raw sensor topics begin after its record start; NTU began at offset 0. The identical command was run twice per sample. The subscriber recorded message counts, first/last message-header stamps, stable frame IDs, callback topic sequence, and parser exceptions.

The exact asynchronous callback-order hashes are included as diagnostics, not as a semantic ordering requirement. ROS callback scheduling can interleave two simultaneously published topics differently even when the bag order, per-topic counts, and per-topic timestamp ranges are identical.

## MUN-FRL Lighthouse benchmarking bag

- Bag open/index: PASS (`rosbag v2.0`, indexed, 181.399074 s)
- Replay slice: offset 6 s, duration 8 s (4.41% of bag), primary topics `/velodyne_points` and `/imu/data`
- Playback exit code: 0 for both runs

| Probe | Run 1 | Run 2 | Match |
|---|---:|---:|---|
| LiDAR messages | 80 | 80 | true |
| IMU messages | 3,200 | 3,200 | true |
| LiDAR header range | 1645814029.1979942–1645814037.1659932 | same | true |
| IMU header range | 1645814029.2913105–1645814037.2863620 | same | true |
| LiDAR frame | `velodyne` | `velodyne` | true |
| IMU frame | `imu_link` | `imu_link` | true |
| Parse errors | 0 | 0 | true |
| Callback topic-order SHA-256 | `6b0aa5ea6ed576f6af160ea555fd3ca36096d326d187e763199c6438ba26cfe2` | `43506ea41e767227c129f0b82f5ff5a9b376263cd5adf438980b2e09ac5f62bc` | scheduling-level interleaving differs |

Result: `SHORT_REPLAY_PASS=true`. Per-topic order, counts, ranges, frames, and parsing are deterministic. The callback interleaving hash is not identical and is retained as a P2 diagnostic.

## NTU VIRAL eee_03

- Bag open/index: PASS (`rosbag v2.0`, indexed, 181.353318 s)
- Replay slice: offset 0 s, duration 8 s (4.41% of bag), primary topics `/os1_cloud_node1/points` and `/imu/imu`
- Playback exit code: 0 for both runs

| Probe | Run 1 | Run 2 | Match |
|---|---:|---:|---|
| LiDAR messages | 80 | 80 | true |
| IMU messages | 3,066 | 3,066 | true |
| LiDAR header range | 1609060334.7743860–1609060342.6649044 | same | true |
| IMU header range | 1609060334.7582874–1609060342.7520647 | same | true |
| LiDAR frame | `sensor1/os_sensor` | `sensor1/os_sensor` | true |
| IMU frame | `imu` | `imu` | true |
| Parse errors | 0 | 0 | true |
| Callback topic-order SHA-256 | `5657865679a5d9bc0bb0b766bee273fd9e83fe3f56c84d34961f132ecceb2643` | `41eb9c8a74c62584b985207c47011ab872d14a945983957e822982d335664a53` | scheduling-level interleaving differs |

Result: `SHORT_REPLAY_PASS=true`. This establishes parse/replay viability only. It does not remove the dataset publisher's documented Ouster/IMU timing-jitter warning; Day 8 must apply and test the official regularization approach before any algorithm run.

## Offline cross-check

Head, middle, and tail messages were also inspected outside playback. Both samples had nondecreasing LiDAR and primary-IMU header timestamps, zero negative timestamp jumps, stable frame IDs, finite sampled IMU values, and zero parser failures. MUN's bag-record epoch and message-header epoch differ, so the adapter must use message headers. NTU's point `t` spans approximately 0–100,030,550 ns per scan and must be treated as nanoseconds.

SHORT_REPLAY_PASS_COUNT: 2
