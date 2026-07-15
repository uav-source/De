# Stage 1 Day 7 Minimal Download Plan v1

- Audit label date: 2026-07-26
- Execution environment date: 2026-07-15
- Plan recorded before download: 2026-07-15T18:18:15+08:00
- Limits: at most 3 selected sources; at most 4 GiB per downloaded source; at most 10 GiB total.
- Available disk before download: 117 GiB.
- Scope: complete official minimal samples only; no truncated archive, range-only pseudo-sample, or full dataset.

## Selection decision

The selected download set is MUN-FRL `Lighthouse_benchmarking_bag` plus NTU VIRAL `eee_03`. MUN-FRL is the preferred MINOR/UAV sample. Newer College Extension `Stairs` was the required open-control preference, but its official Google Drive file returned the provider's "too many users" quota error during the preflight request. NTU `eee_03`, an official outdoor central-carpark UAV sequence from the same EEE location family recommended for Day 6 open control, is therefore the bounded fallback needed to complete two actual source checks. Newer remains the third selected source in `HOLD_ACCESS`; Hilti and SubT-MRS are non-selected holds.

The MUN and final NTU byte sizes were resolved without downloading their selected payloads. Both are individually below 4 GiB (4,294,967,296 bytes), and their sum is 5,808,136,874 bytes (5.41 GiB), below the 10 GiB total limit.

Plan amendment at 2026-07-15T18:22:17+08:00: the initial NTU `rtp_03` Dataverse request was stopped after 6,946,816 bytes because sustained throughput was unsuitable for a bounded audit. The official site's documented OneDrive backup did not contain the newer RTP family, but it did contain `eee_03`; SharePoint reported 1,995,367,404 bytes, exactly matching NTU Dataverse metadata and its official MD5. The incomplete RTP file is retained as an aborted transfer record and is not treated as a downloaded sample.

## Candidate plan

| dataset_id | dataset_name | selected_sequence | selection_reason | official_download_page | official_file_url | official_license_source | expected_size | download_required | registration_required | download_priority | download_status | hold_reason | planned_probe_items |
|---|---|---|---|---|---|---|---:|---|---|---:|---|---|---|
| mun_frl | MUN-FRL | Lighthouse_benchmarking_bag (`lighthouse_francis_sample.bag`) | Smallest official workshop bag; UAV; documented LiDAR, IMU, hardware timestamps and GT topics | https://mun-frl-vil-dataset.readthedocs.io/en/latest/ | https://drive.google.com/file/d/15MovyJSUhj0D2cgWNklvQTru7j6JfUwb/view | https://mun-frl-vil-dataset.readthedocs.io/en/latest/#lisence | 3,812,769,470 bytes | true | false | 1 | PLANNED | none | file hash; ROS bag integrity/info; topics and fields at head/middle/tail; IMU units; documented extrinsic chain; GT topics; two identical short replay probes |
| ntu_viral | NTU VIRAL | eee_03 | Official outdoor central-carpark sequence; smallest complete EEE-family bag archive; MINOR/UAV and bounded open-control fallback | https://ntu-aris.github.io/ntu_viral_dataset/ | https://entuedu-my.sharepoint.com/:f:/g/personal/shyuan_staff_main_ntu_edu_sg/EvyxXbi1l5tHonBWIQxueBoByr1-E-w7fgRyHNTsCmwFcg | https://ntu-aris.github.io/ntu_viral_dataset/#licence | 1,995,367,404 bytes; official Dataverse MD5 `9bf10b5455ee6d2962324ef557f86433` | true | false | 2 | PLANNED | none | archive CRC/path safety; file hash and official MD5; bag info; head/middle/tail Ouster/IMU/GT fields; official jitter condition; calibration direction; two identical short replay probes |
| newer_college_multicam | Newer College Multi-Camera LiDAR-Inertial Extension | Stairs | Shortest recommended extension sequence; complete 10 Hz 6DoF GT; normal/control-format probe without using the Maths evaluation family | https://ori-drs.github.io/newer-college-dataset/download/ | https://drive.google.com/file/d/1ql0C8el5PJs6O0x4xouqaW9n2RZy53q9/view | https://ori-drs.github.io/newer-college-dataset/download/#licence | unknown at preflight | true | form is presented, but the public folder/file is readable without submitting credentials | 3 | HOLD_ACCESS | official file returned Google Drive high-demand quota error; no payload request started | retain official topic/calibration/GT metadata only; do not claim actual field or replay verification |
| hilti_2021 | Hilti SLAM Challenge Dataset 2021 | Basement | Preferred underground/construction sequence | https://www.hilti-challenge.com/dataset-2021 | not requested because the published minimum is already over the limit | https://www.hilti-challenge.com/dataset-2021 | approximately 6 GB | false | false | 4 | HOLD_SIZE | minimal complete Basement sample exceeds the 4 GiB single-source limit | retain sparse 3DoF checkpoint limitation; no download or replay |
| subt_mrs | SubT-MRS | Long_Corridor | Highest tunnel relevance, but Day 6 found no explicit dataset license | https://sairlab.org/subtmrs/ | not requested | no explicit license found on audited official pages | not applicable | false | false | 5 | HOLD_LICENSE | written use terms are required before acquisition | no download; preserve `HOLD_LICENSE` |

## Preflight release conditions

1. Abort a payload if the resolved size exceeds 4 GiB or would push the aggregate above 10 GiB.
2. Use resumable official-host downloads and retain start/end/result logs outside Git.
3. Do not extract an archive until its size and checksum are recorded and its member paths are safe.
4. Do not label a sample READY unless actual point fields, point-time mechanism/unit, IMU units, monotonicity, LiDAR–IMU transform direction, and reference format are verified.
5. Do not run FAST-LIO2, ODI, trajectory alignment, ATE, or RPE.
