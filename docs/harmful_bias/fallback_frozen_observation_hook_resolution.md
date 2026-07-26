# Fallback B compact export capability resolution

| feature | source_file | symbol | line_range | source_sha256 | status | notes |
|---|---|---|---:|---|---|---|
| minimal payload profile | `include/readonly_observation_tap.hpp` | `TapPayloadProfile::DETECTOR_MINIMAL_V1` | 37-40 | `b8be868fe3a18cf68711256ef00302df38f6a2922cae3b5aa42cd4e93fbafec1` | CONFIRMED | Existing bounded payload profile. |
| bounded tap buffers | `include/readonly_observation_tap.hpp` | `TapConfig::buffer_capacity` and deques | 48, 217-218 | `b8be868fe3a18cf68711256ef00302df38f6a2922cae3b5aa42cd4e93fbafec1` | CONFIRMED | Capacity is fixed to 1024 by the runner. No background thread exists. |
| compact payload encoding | `src/readonly_observation_binary_writer.cpp` | `encodePayload` | 52-112 | `468b46d3f24e36daf32ccf5a91c59f631817a7f7d38cef0a57d05d6b81e6d2ee` | CONFIRMED | Minimal payload contains detector J/h and checksums, not complete neighbors or plane arrays. |
| binary magic/version | `include/readonly_observation_binary_writer.hpp`, `src/readonly_observation_binary_writer.cpp` | `kObservationBinaryVersion`, `kMagic`, `writeHeader` | 14, 12-16, 160-166 | `1525a81c71d5a2c36f1607340812c0c11118ba311bf4910c6614afc452045b84`, `468b46d3f24e36daf32ccf5a91c59f631817a7f7d38cef0a57d05d6b81e6d2ee` | CONFIRMED | Magic `HBROBSV3`, version 3, little endian, 16-byte header. |
| record checksum | `src/readonly_observation_binary_writer.cpp` | `writeObservation` | 169-190 | `468b46d3f24e36daf32ccf5a91c59f631817a7f7d38cef0a57d05d6b81e6d2ee` | CONFIRMED | FNV-1a over exact payload bytes. |
| file trailer | `src/readonly_observation_binary_writer.cpp` | `ReadonlyObservationBinaryWriter::close` | 220-234 | `468b46d3f24e36daf32ccf5a91c59f631817a7f7d38cef0a57d05d6b81e6d2ee` | CONFIRMED | `HBRENDV1`, record count, and complete pre-trailer file checksum. |
| non-realtime export | `src/laserMapping.cpp` | `drainReadonlyTapRecords` | 331-361 | `796ddeb709792a493fcbebbd91fb20a9a70f7aee9b5aef65cd83b36b9184f485` | CONFIRMED | Drains the bounded record buffer after the formal scan path; no JSON formatting in the measurement-model call. |
| compact-export mode | `src/laserMapping.cpp` | `RuntimeMode::COMPACT_EXPORT` | 1274-1337 | `796ddeb709792a493fcbebbd91fb20a9a70f7aee9b5aef65cd83b36b9184f485` | CONFIRMED | Enables the existing tap and binary writer without detector execution. |
| writer finalization and summary | `src/laserMapping.cpp` | writer close and `tap_export_summary.json` | 1651-1682 | `796ddeb709792a493fcbebbd91fb20a9a70f7aee9b5aef65cd83b36b9184f485` | CONFIRMED | Emits count/drop/error summaries after normal shutdown. |
| existing converter | `scripts/46_convert_fastlio2_runtime_binary.py` | `read_framed_binary`, `decode_observation_record` | 57-115, 258-340 | recorded in the run lock | CONFIRMED | Reused without semantic modification through a read-only freeze wrapper. |
| tail-clock/drain/shutdown | `scripts/60_run_single_startup_sync_v5.py` | frozen V5 transport | 480-1035 | recorded in the run lock | CONFIRMED | Paused start, handshake, tail clock, drain, and normal shutdown are reused. |

`COMPACT_EXPORT_CAPABILITY_CONFIRMED=true`.

No FAST-LIO2 source, binary, sampling rule, writer, schema, or in-call audit
is modified by Fallback B.
