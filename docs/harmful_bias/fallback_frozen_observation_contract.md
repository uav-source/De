# Day 5 Fallback B frozen observation contract

Fallback B performs one engineering replay of `avia_quick_shack` with the
existing read-only tap in `COMPACT_EXPORT` mode. It freezes the complete
`HBROBSV3` observation binary and derives only bounded metadata, an index,
validation summaries, provenance, and integrity evidence.

The record source is `FASTLIO2_RUNTIME_COMPACT_BINARY`, the record schema is
`readonly_observation_v3`, the payload profile is `DETECTOR_MINIMAL_V1`, and
the checksum algorithm is `FNV1A64_EXACT_BYTES_V1`.

The existing converter is reused without changing its binary semantics.
Fallback B adds byte-offset indexing, lifecycle reconciliation, fail-closed
schema validation, no-GT scanning, deterministic archive generation, and
round-trip verification. Converted full observation JSON and runtime CSV are
not copied into the frozen artifact or audit archive.

The data identity is internal engineering development evidence only:

- scientific label status: `UNVERIFIED`
- ground-truth-label eligibility: false
- AUROC-label eligibility: false
- holdout/test evidence: false
- redistribution authorization: false

No production detector, ODI, AIS, eigengap, weak-direction computation,
Development, Holdout, Future Test, GT topic, future frame, or manual role is
allowed.

Passing this contract authorizes only an offline production-detector
determinism step. Day 6, statistical replay tolerance, FAST-LIO2 integration,
and formal Degen-LIO remain unauthorized.
