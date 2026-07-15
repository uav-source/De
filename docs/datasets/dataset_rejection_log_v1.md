# Dataset Rejection and Hold Log v1

- Audit label date: 2026-07-25
- Execution date: 2026-07-15

No whole candidate dataset was marked `REJECTED`. This avoids manufacturing a rejection merely to populate a category. The following holds and sequence-level exclusions are binding.

## Dataset-level hold

| Dataset | State | Reason | Release condition |
|---|---|---|---|
| SubT-MRS | LIMITED_USE | No explicit dataset license or redistribution terms were found on the audited official project/data/paper pages | Written license/use clarification plus a small LiDAR+IMU schema probe |

## Sequence-level exclusions from primary ATE

| Dataset/sequence class | Exclusion | Reason |
|---|---|---|
| Hilti sequences with 3DoF total-station points | No primary full-trajectory ATE/RPE | Ground truth is sparse and stationary; use checkpoint translation error only |
| NTU VIRAL all sequences | No independent rotation-GT metric | Official documentation states no orientation ground truth |
| MulRan ParkingLot sample | Not an LIO sample | Official page states the small sample has no IMU and GPS |
| HeLiPR KAIST04/DCC04/Riverside04 | No LIO experiment | Official sequence page states sequence04 has no IMU |
| TIERS Indoor06-11 | No “independent external GT” wording | Reference is SLAM-assisted ICP; provenance must be explicit |
| MUN-FRL Bell412 sequences | Not first adapter target | Published evaluation reports FAST-LIO2 failure and limited useful LiDAR in structureless flight segments |
| Any sequence with unverified point timing/extrinsic direction | No formal experiment | A deterministic sample-level schema audit is required first |

## Candidates not promoted to Priority A

- M2DGR: download volume and host stability make it Priority B despite excellent GT.
- TIERS: valuable corridor/sensor data, but heterogeneous custom preprocessing and GT provenance make it Priority B.
- MulRan: conversion and per-point timing uncertainty make it Priority C.
- HeLiPR: asynchronous heterogeneous files and size make it Priority C.

This log is a feasibility decision, not a statement that the underlying datasets are scientifically poor.
