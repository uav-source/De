# Fallback B Offline Archive Remediation V1

## Scope

This remediation changes only the offline archive protocol for the already
frozen Quick Shack observation evidence. It does not collect, regenerate,
delete, or reorder any observation record. FAST-LIO2, ROS, rosbag, the
production detector, ODI, Development, Holdout, and Future Test were not run.

The previous frozen archive and main audit package remain unchanged. Their
identities are recorded by SHA-256 in the remediation manifest.

## Defects corrected

The previous frozen artifact contained two personal runtime paths in:

- `INTEGRITY_SUMMARY.json`
- `binary/binary_validation_summary.json`

Both `path` fields were replaced by:

`path_alias = binary/observation_records_v3.bin`

No raw personal path is retained in the remediated artifact. The artifact root
and every directory are explicitly normalized to `0755`; every regular file is
normalized to `0644`. Content scanning now examines bounded UTF-8 text, and the
mode audit covers the root, directories, regular files, links, and special
entries.

## Core data integrity

The observation binary remains byte-for-byte identical:

`d7f218068868985eee7ff01a8b7d1ce3467711d088e8c00b6c5de04ff0c120f3`

The binary size, 487 record frames, trailer count, index row order, scan-index
sequence, binary-offset sequence, lifecycle counts, schema counts, no-GT
counts, drop counts, and writer-error counts are unchanged.

## Remediated artifact

Artifact version `1.1` is an `OFFLINE_ARCHIVE_PROTOCOL_FIX`. Two deterministic
builds are byte-identical with SHA-256:

`f68c9671e0058644b86fd1602b44b4a19ee35714e523cc10e1261650d538aca8`

Round-trip verification passes internal hashes, content-path scanning, mode
normalization, binary and trailer validation, record index, lifecycle, schema,
and no-GT checks.

## Scientific and authorization boundary

The data remains internal engineering development evidence with
`scientific_label_status=UNVERIFIED`. It is not ground truth, AUROC-label
evidence, holdout, future test evidence, or redistributable material.

This remediation does not prove cross-process bitwise replay equivalence and
does not authorize Day 6. Passing the archive gates preserves only the existing
authorization to perform a later, separate Fallback C offline production
detector determinism check.
