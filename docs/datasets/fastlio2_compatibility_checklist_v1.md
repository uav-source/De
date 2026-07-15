# FAST-LIO2 Compatibility Checklist v1

- Audit label date: 2026-07-25
- Execution/source-check date: 2026-07-15
- Scope: documentation-only feasibility audit. No dataset was downloaded, converted, or replayed.
- Decision vocabulary: `DIRECT`, `MINOR_ADAPTER`, `MAJOR_ADAPTER`, `NOT_COMPATIBLE`, `UNKNOWN`.

`DIRECT` is deliberately not assigned from a ROS bag label alone. A formal run requires a sample-level assertion of point fields, time units, frame direction, topic mapping, deterministic replay, and reference-trajectory semantics.

## 1. SubT-MRS — `MAJOR_ADAPTER`

| Check | Finding |
|---|---|
| Per-point timestamp | `UNKNOWN`; bag/LAS availability does not prove a uniform per-point time field across robots. |
| Ring or equivalent | `UNKNOWN`; sequence and sensor dependent. |
| Point-cloud coordinate definition | `PARTIAL`; platform/sensor calibration is published, but a selected sequence must be checked. |
| LiDAR time units | `UNKNOWN`; inspect the selected bag or packet decoder. |
| IMU time units | `UNKNOWN`; inspect the selected bag. |
| Gyroscope units | `UNKNOWN`; verify message type and metadata. |
| Accelerometer units | `UNKNOWN`; verify message type and metadata. |
| LiDAR–IMU extrinsic direction | `PARTIAL`; calibration resources exist, but transform direction must be resolved per platform. |
| Sufficient IMU frequency | `PARTIAL`; LiDAR+IMU platforms exist, but rate is sequence dependent. |
| Hardware synchronization | `YES`; the official collection describes hardware synchronization, subject to sequence confirmation. |
| ROS bag topics | `PARTIAL`; ROS bags are released, but topic names vary by platform. |
| PointCloud2 fields | `UNKNOWN`; inspect one selected LiDAR+IMU sequence. |
| Custom preprocessing | `REQUIRED`; normalize the selected robot/sensor schema and reject modality-only sequences. |
| Bag conversion | `POSSIBLE`; use an existing bag when complete, otherwise packet/LAS conversion is a major task. |
| Deterministic replay | `UNVERIFIED`; requires a fixed converter, topic map, and timestamp assertions. |
| Data loss/time jumps | `UNKNOWN`; no blanket claim is made across the heterogeneous release. |
| Independent reference trajectory | `PARTIAL`; reference files exist, but coverage and provenance must be verified sequence by sequence. |

Conclusion: `MAJOR_ADAPTER`. `Long_Corridor` remains conditional on license clarification and a small schema probe.

## 2. Hilti SLAM Challenge 2021 — `MAJOR_ADAPTER`

| Check | Finding |
|---|---|
| Per-point timestamp | `UNKNOWN`; exact Ouster/Livox point-time fields are not established by the dataset page. |
| Ring or equivalent | `UNKNOWN`; inspect PointCloud2 and Livox `CustomMsg`. |
| Point-cloud coordinate definition | `PARTIAL`; TF and calibration are supplied. |
| LiDAR time units | `UNKNOWN`; inspect message definitions and sample values. |
| IMU time units | `PARTIAL`; ROS timestamps are available, exact source time semantics require inspection. |
| Gyroscope units | `PARTIAL`; ADIS16445 data are present, sample-level unit assertion is required. |
| Accelerometer units | `PARTIAL`; ADIS16445 data are present, sample-level unit assertion is required. |
| LiDAR–IMU extrinsic direction | `PARTIAL`; TF/calibration exist, but the transform consumed by FAST-LIO2 must be resolved explicitly. |
| Sufficient IMU frequency | `YES`; the official sensor setup is intended for LiDAR-inertial SLAM. |
| Hardware synchronization | `YES`; official documentation reports alignment within 1 ms. |
| ROS bag topics | `YES`; data are released as ROS bags. |
| PointCloud2 fields | `UNKNOWN`; Ouster and Livox schemas require inspection. |
| Custom preprocessing | `REQUIRED`; select one LiDAR and one IMU, map PointCloud2 or `CustomMsg`, and assert frames. |
| Bag conversion | `NOT_EXPECTED` for bag transport; message adaptation is still required. |
| Deterministic replay | `UNVERIFIED`; establish fixed topic selection and preprocessing. |
| Data loss/time jumps | `UNKNOWN`; check the selected sequence. |
| Independent reference trajectory | `PARTIAL`; most sequences have sparse 3DoF total-station control, while only named arena/lab sequences provide 6DoF reference. |

Conclusion: `MAJOR_ADAPTER`. Basement data support sparse checkpoint analysis, not blanket full-trajectory ATE.

## 3. Newer College Original — `MAJOR_ADAPTER`

| Check | Finding |
|---|---|
| Per-point timestamp | `PARTIAL`; raw Ouster packets are available, but the processed-cloud schema is not enumerated. |
| Ring or equivalent | `UNKNOWN`; inspect the processed message or decode raw packets. |
| Point-cloud coordinate definition | `PARTIAL`; calibration and TF resources are published. |
| LiDAR time units | `UNKNOWN`; verify decoded/processed point time units. |
| IMU time units | `UNKNOWN`; inspect ROS message values and timestamps. |
| Gyroscope units | `UNKNOWN`; assert from the sample message and sensor documentation. |
| Accelerometer units | `UNKNOWN`; assert from the sample message and sensor documentation. |
| LiDAR–IMU extrinsic direction | `PARTIAL`; published calibration must be converted to FAST-LIO2's expected direction. |
| Sufficient IMU frequency | `YES`; the Ouster/RealSense inertial streams are intended for LiDAR-inertial evaluation. |
| Hardware synchronization | `NO`; the original release documents software synchronization. |
| ROS bag topics | `YES`; official topic/rate documentation and bag downloads exist. |
| PointCloud2 fields | `UNKNOWN`; a schema dump is required. |
| Custom preprocessing | `REQUIRED`; either map the processed cloud or deterministically decode raw Ouster packets. |
| Bag conversion | `POSSIBLE`; no transport conversion if using bags, packet conversion may be needed for timing. |
| Deterministic replay | `UNVERIFIED`; fix decoder/version and synchronization policy. |
| Data loss/time jumps | `UNKNOWN`; inspect sequence timestamp monotonicity. |
| Independent reference trajectory | `YES`; the survey-map pipeline supplies centimetre-level 6DoF ground truth at 10 Hz. |

Conclusion: `MAJOR_ADAPTER` until the Ouster point schema and software-sync behavior pass a small probe.

## 4. Newer College Multi-Camera Extension — `MAJOR_ADAPTER`

| Check | Finding |
|---|---|
| Per-point timestamp | `PARTIAL`; raw Ouster packets are available, processed field layout is not explicit. |
| Ring or equivalent | `UNKNOWN`; inspect PointCloud2 or decoded packets. |
| Point-cloud coordinate definition | `PARTIAL`; calibration/TF resources are published. |
| LiDAR time units | `UNKNOWN`; verify sample fields and units. |
| IMU time units | `UNKNOWN`; verify sample fields and units. |
| Gyroscope units | `UNKNOWN`; assert from the selected message. |
| Accelerometer units | `UNKNOWN`; assert from the selected message. |
| LiDAR–IMU extrinsic direction | `PARTIAL`; calibration exists; consuming direction remains an adapter assertion. |
| Sufficient IMU frequency | `YES`; official sensor rates support LiDAR-inertial processing. |
| Hardware synchronization | `YES`; the extension documents hardware synchronization. |
| ROS bag topics | `YES`; official sequence bags and topic/rate information are provided. |
| PointCloud2 fields | `UNKNOWN`; schema dump required before formal use. |
| Custom preprocessing | `REQUIRED`; deterministic Ouster field mapping or packet decoding. |
| Bag conversion | `POSSIBLE`; bag transport is available, raw-packet conversion may be selected. |
| Deterministic replay | `UNVERIFIED`; pin decoder and topic/frame mapping. |
| Data loss/time jumps | `UNKNOWN`; check each selected sequence. |
| Independent reference trajectory | `YES`; centimetre-level 6DoF ground truth is provided at 10 Hz. |

Conclusion: `MAJOR_ADAPTER`; this may be reduced only after a successful field/time probe.

## 5. NTU VIRAL — `MINOR_ADAPTER`

| Check | Finding |
|---|---|
| Per-point timestamp | `YES`; official PointCloud2 documentation specifies field `t`. |
| Ring or equivalent | `YES`; official PointCloud2 documentation specifies field `ring`. |
| Point-cloud coordinate definition | `YES`; sensor frames and calibration are documented. |
| LiDAR time units | `PARTIAL`; the `t` field exists, but its numeric unit must still be asserted in the adapter. |
| IMU time units | `PARTIAL`; ROS timestamps are documented along with jitter handling. |
| Gyroscope units | `PARTIAL`; VN-100 raw IMU is documented; assert ROS SI units in the probe. |
| Accelerometer units | `PARTIAL`; VN-100 raw IMU is documented; assert ROS SI units in the probe. |
| LiDAR–IMU extrinsic direction | `YES`; official calibration and sensor-frame documentation are available. |
| Sufficient IMU frequency | `YES`; VN-100 raw IMU is approximately 385 Hz. |
| Hardware synchronization | `PARTIAL`; the release documents Ouster/IMU jitter that requires official regularization. |
| ROS bag topics | `YES`; official topic names, types, and rates are documented. |
| PointCloud2 fields | `YES`; at least `x,y,z,intensity,t,reflectivity,ring,ambient,range` are documented. |
| Custom preprocessing | `REQUIRED`; apply the official regularization and map the documented Ouster fields. |
| Bag conversion | `NOT_EXPECTED`; official bags are supplied. |
| Deterministic replay | `PARTIAL`; achievable by pinning and hashing the official regularization output. |
| Data loss/time jumps | `KNOWN_LIMITATION`; documented timestamp jitter must be normalized and audited. |
| Independent reference trajectory | `PARTIAL`; Leica tracking supplies 20 Hz position only, with no orientation GT and a 0.4 m IMU–prism offset. |

Conclusion: `MINOR_ADAPTER`. Formal use requires deterministic regularization and position-only metric boundaries.

## 6. M2DGR — `MAJOR_ADAPTER`

| Check | Finding |
|---|---|
| Per-point timestamp | `UNKNOWN`; official public documentation does not enumerate the VLP-32C point fields. |
| Ring or equivalent | `UNKNOWN`; inspect PointCloud2. |
| Point-cloud coordinate definition | `PARTIAL`; sensor setup and calibration are published. |
| LiDAR time units | `UNKNOWN`; inspect sample values. |
| IMU time units | `UNKNOWN`; inspect the chosen IMU topic. |
| Gyroscope units | `UNKNOWN`; several IMUs are present, so select and assert one stream. |
| Accelerometer units | `UNKNOWN`; several IMUs are present, so select and assert one stream. |
| LiDAR–IMU extrinsic direction | `PARTIAL`; calibration exists; direction must be resolved for the chosen IMU. |
| Sufficient IMU frequency | `YES`; the platform contains multiple high-rate inertial sensors. |
| Hardware synchronization | `YES`; the release describes calibrated and synchronized sensors. |
| ROS bag topics | `YES`; official topic documentation and bags are provided. |
| PointCloud2 fields | `UNKNOWN`; dump the selected VLP-32C message schema. |
| Custom preprocessing | `REQUIRED`; select one IMU, map point timing/ring, and resolve frames. |
| Bag conversion | `NOT_EXPECTED` for official bag transport. |
| Deterministic replay | `UNVERIFIED`; requires fixed topic selection and timing assertions. |
| Data loss/time jumps | `UNKNOWN`; inspect the selected sequence. |
| Independent reference trajectory | `YES`; scenario-specific RTK, Leica, or Vicon full references are provided, with provenance retained per sequence. |

Conclusion: `MAJOR_ADAPTER`; use one small full-GT sequence for schema inspection, not the 1.22 TB release.

## 7. MulRan — `MAJOR_ADAPTER`

| Check | Finding |
|---|---|
| Per-point timestamp | `NO/UNKNOWN`; raw OS1 scans are `.bin` frames without a documented per-point time field. |
| Ring or equivalent | `DERIVED`; the official player reconstructs/synthesizes ring information rather than proving a raw field. |
| Point-cloud coordinate definition | `PARTIAL`; sensor calibration/player resources exist. |
| LiDAR time units | `PARTIAL`; frame stamps are released separately; within-scan time needs a model. |
| IMU time units | `PARTIAL`; IMU/GPS CSV stamps exist in the full release. |
| Gyroscope units | `UNKNOWN`; verify the official CSV schema. |
| Accelerometer units | `UNKNOWN`; verify the official CSV schema. |
| LiDAR–IMU extrinsic direction | `PARTIAL`; calibration resources exist; conversion direction needs assertion. |
| Sufficient IMU frequency | `PARTIAL`; IMU is released, but the selected route/sample must be checked. |
| Hardware synchronization | `UNKNOWN`; do not infer it from timestamp files. |
| ROS bag topics | `NO` in raw release; an official file player publishes ROS topics. |
| PointCloud2 fields | `DERIVED`; determined by the player/converter, not the raw `.bin` file. |
| Custom preprocessing | `REQUIRED`; deterministic files-to-PointCloud2 conversion and point-time policy. |
| Bag conversion | `REQUIRED`; official player support exists, but combined bag generation is not a complete turnkey path. |
| Deterministic replay | `UNVERIFIED`; pin converter and output hashes. |
| Data loss/time jumps | `UNKNOWN`; audit CSV/scan stamp continuity. |
| Independent reference trajectory | `PARTIAL`; a 6DoF baseline/reference is released, but provenance must be stated rather than assumed independent. |

Conclusion: `MAJOR_ADAPTER`. The small ParkingLot sample is excluded because it has no IMU/GPS.

## 8. HeLiPR — `MAJOR_ADAPTER`

| Check | Finding |
|---|---|
| Per-point timestamp | `UNKNOWN`; sensor-specific `.bin` formats and stamp files need parser-level inspection. |
| Ring or equivalent | `SENSOR_DEPENDENT`; four heterogeneous LiDARs require separate checks. |
| Point-cloud coordinate definition | `PARTIAL`; system geometry/extrinsics are published. |
| LiDAR time units | `PARTIAL`; per-sensor stamp files exist, point-level semantics are parser dependent. |
| IMU time units | `PARTIAL`; Xsens raw timestamps/topics are documented, sample assertion remains. |
| Gyroscope units | `PARTIAL`; Xsens raw IMU is present; verify parser output units. |
| Accelerometer units | `PARTIAL`; Xsens raw IMU is present; verify parser output units. |
| LiDAR–IMU extrinsic direction | `PARTIAL`; extrinsics are expressed relative to the IMU, but adapter direction must be checked. |
| Sufficient IMU frequency | `YES`; Xsens IMU is 100 Hz. |
| Hardware synchronization | `NO/PARTIAL`; LiDARs are intentionally asynchronous and timestamps are supplied per sensor. |
| ROS bag topics | `PARTIAL`; some sensor/IMU resources use ROS topics, while main LiDAR data are sensor files. |
| PointCloud2 fields | `UNKNOWN`; determined by each official/custom parser. |
| Custom preprocessing | `REQUIRED`; one deterministic parser per chosen LiDAR plus common frame/time normalization. |
| Bag conversion | `REQUIRED`; main sensor files must be converted or replayed through a fixed publisher. |
| Deterministic replay | `UNVERIFIED`; pin parsers and timestamp ordering. |
| Data loss/time jumps | `UNKNOWN`; audit each sensor stamp series; sequence04 additions lack IMU. |
| Independent reference trajectory | `PARTIAL`; per-LiDAR INS-derived 6DoF references exist, but are not a wholly independent external pose system. |

Conclusion: `MAJOR_ADAPTER`; use the one-minute sample only for packaging inspection before any main sequence.

## 9. TIERS Enhanced — `MAJOR_ADAPTER`

| Check | Finding |
|---|---|
| Per-point timestamp | `UNKNOWN`; Ouster/VLP/Livox schemas are not uniformly enumerated. |
| Ring or equivalent | `SENSOR_DEPENDENT`; inspect PointCloud2 and Livox `CustomMsg`. |
| Point-cloud coordinate definition | `PARTIAL`; calibration/frame tools exist, exact target frame needs resolution. |
| LiDAR time units | `UNKNOWN`; inspect each selected LiDAR message. |
| IMU time units | `UNKNOWN`; inspect selected bag/topic. |
| Gyroscope units | `UNKNOWN`; assert from sample messages. |
| Accelerometer units | `UNKNOWN`; assert from sample messages. |
| LiDAR–IMU extrinsic direction | `UNKNOWN/PARTIAL`; calibration resources exist, direction requires a sample audit. |
| Sufficient IMU frequency | `PARTIAL`; LiDAR-inertial bags exist, verify the selected sequence rate. |
| Hardware synchronization | `PARTIAL`; official paper reports sensor time offsets within approximately 5 ms. |
| ROS bag topics | `YES`; enhanced data are released as ROS bags. |
| PointCloud2 fields | `UNKNOWN`; heterogeneous schemas require dumps. |
| Custom preprocessing | `REQUIRED`; choose one LiDAR and normalize its message/frame/time representation. |
| Bag conversion | `NOT_EXPECTED` for bag transport; heterogeneous message adaptation remains. |
| Deterministic replay | `UNVERIFIED`; fix one sensor configuration and topic map. |
| Data loss/time jumps | `UNKNOWN`; audit selected Indoor/Road sequences. |
| Independent reference trajectory | `PARTIAL`; RTK/MoCap are available for some scenes, while indoor reference is SLAM-assisted ICP. |

Conclusion: `MAJOR_ADAPTER`; do not describe the indoor reference as independent external GT.

## 10. MUN-FRL — `MINOR_ADAPTER`

| Check | Finding |
|---|---|
| Per-point timestamp | `PARTIAL`; official FAST-LIO material demonstrates usability, but exact sample field layout must be asserted. |
| Ring or equivalent | `PARTIAL`; VLP-16 geometry is supported, exact PointCloud2 field needs a schema dump. |
| Point-cloud coordinate definition | `YES`; calibration and platform/sensor frames are documented. |
| LiDAR time units | `UNKNOWN/PARTIAL`; verify the synchronized bag's point-time representation. |
| IMU time units | `PARTIAL`; synchronized Xsens streams are supplied; assert values/units. |
| Gyroscope units | `PARTIAL`; Xsens data are documented, assert ROS SI units. |
| Accelerometer units | `PARTIAL`; Xsens data are documented, assert ROS SI units. |
| LiDAR–IMU extrinsic direction | `PARTIAL`; calibration exists, but FAST-LIO2 input direction must be checked. |
| Sufficient IMU frequency | `YES`; Xsens IMU is recorded at 400 Hz. |
| Hardware synchronization | `YES`; PPS/hardware synchronization and synchronized bags are documented. |
| ROS bag topics | `YES`; synchronized and raw bags are released. |
| PointCloud2 fields | `UNKNOWN/PARTIAL`; dump the VLP-16 message before the first run. |
| Custom preprocessing | `REQUIRED`; small topic/frame/time mapping plus assertions. |
| Bag conversion | `NOT_EXPECTED`; official synchronized bags and FAST-LIO launch/evaluation material exist. |
| Deterministic replay | `PARTIAL`; likely achievable from synchronized bags, but must be demonstrated and hashed. |
| Data loss/time jumps | `UNKNOWN`; audit the selected Lighthouse bag before formal use. |
| Independent reference trajectory | `PARTIAL/YES`; PPK position references are external; published 6DoF references may include aided estimation and must retain provenance. |

Conclusion: `MINOR_ADAPTER`. The 3.55 GB Lighthouse benchmarking bag is the recommended first later download; Bell412 is reserved as a later documented failure case.

## Cross-dataset release condition

Before any formal experiment, the selected dataset must pass all of the following with recorded evidence: exact topics and message types; PointCloud2/custom fields; point and header time units; monotonicity and loss checks; gyro/accelerometer units; explicit transform direction; IMU rate; deterministic preprocessing/replay hash; and reference-trajectory coverage/provenance. Day 6 does not claim that any candidate has passed that sample-level gate.
