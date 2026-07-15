# Stage 1 Day 7 FAST-LIO2 Adapter Release Matrix v1

“READY” here means only that the input contract is sufficiently explicit to begin adapter work. It does not mean FAST-LIO2 has run, localization has succeeded, real-data ODI has been validated, or the adapter exists.

| Dataset / sequence | Evidence completed | Difficulty | Release status | Day 8 disposition |
|---|---|---|---|---|
| MUN-FRL / Lighthouse benchmarking bag | Actual ROS bag, head/middle/tail fields, point time in seconds, ring, SI IMU, monotonic headers, official-linked LiDAR-in-IMU transform, position-only RTK, two short replays | MINOR | `READY_MINOR_ADAPTER` | First adapter target |
| NTU VIRAL / eee_03 | Official-checksum ZIP, actual Ouster fields, nanosecond `t`, ring, VN100 SI IMU, archive `T_Body_Lidar`, position-only Leica GT, two short replays | MAJOR | `READY_MAJOR_ADAPTER` | Second target after a guarded timing/config preprocessing branch |
| Newer College Extension / Stairs | Official metadata only; payload quota-blocked | UNKNOWN | `BLOCKED_DOWNLOAD` | No implementation based on guessed fields |
| Hilti 2021 / Basement | Not selected; minimum exceeds source cap | UNKNOWN | `NOT_SELECTED` | Preserve checkpoint-only GT semantics |
| SubT-MRS / Long_Corridor | No explicit license established | UNKNOWN | `HOLD_LICENSE` | No download or adapter work |

## Release reasoning

MUN-FRL satisfies every READY condition. Its VLP-16 fields are `x,y,z,intensity,ring,time`, the actual `time` samples are scan-relative seconds, `/imu/data` is SI `sensor_msgs/Imu`, and the official dataset-linked FAST-LIO configuration gives the LiDAR pose directly in the IMU body frame. Its main cautions are the workshop bag's record/header epoch mismatch and position-only raw RTK topic.

NTU VIRAL also has a complete adapter input contract, but it is classified MAJOR because preprocessing is mandatory. The checksum-verified archive is authoritative: it states 16 horizontal channels and a 4x4 `T_Body_Lidar`; `T_Body_Imu=I`, so no inversion is required. The official-site-linked FAST-LIO configuration correctly identifies the topics, nanosecond unit, translation, and `-0.1 s` offset, but its `scan_line: 32` and 12-value `extrinsic_R` must not be copied literally. The adapter must use 16 channels and a valid 3x3 identity rotation from the archive, and must address the dataset's documented timing jitter.

## Counts

- `READY_MINOR_ADAPTER_COUNT=1`
- `READY_MAJOR_ADAPTER_COUNT=1`
- `READY_METADATA_ONLY_COUNT=0`
- `BLOCKED_SAMPLE_COUNT=1`
- `HOLD_LICENSE_COUNT=1`

The field-by-field machine-readable decision is in `day7_fastlio2_adapter_release_matrix_v1.csv`.
