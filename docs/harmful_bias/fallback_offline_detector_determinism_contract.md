# Fallback C Offline Production Detector Determinism Contract

This bounded task uses only the frozen 487-record observation artifact, the existing runtime production-detector adapter, and the locked production detector/config. It preserves record order, maps the Jacobian without reordering, expands the scalar variance to float64, and does not pass residuals or prior covariance into detector mathematics.

Canonical output uses sorted compact UTF-8 JSON, `allow_nan=False`, one LF, and a SHA-256 self-checksum excluding only its own field. The immutable v3 schema is reused through an explicit source projection; persisted offline records use `record_source=FROZEN_REAL_OBSERVATION`.

All three fresh processes and direct production equivalence are mandatory. Any incomplete run or mismatch closes Fallback C and cannot authorize Day 6.
