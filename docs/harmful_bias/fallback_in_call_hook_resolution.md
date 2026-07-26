# Fallback In-Call Hook Resolution

Status: `CONFIRMED`

This resolution is for the current FAST-LIO2 working tree only. The source
identity used for the resolution is:

- branch: `spike/readonly-observation-tap-v1`
- HEAD: `f19b4c42a77dc11793c912d67b9e56dcafa279dc`
- file: `src/laserMapping.cpp`
- source SHA-256:
  `796ddeb709792a493fcbebbd91fb20a9a70f7aee9b5aef65cd83b36b9184f485`
- symbol: `h_share_model`
- formal J/h construction: lines 1036-1068
- in-call pre/tap/post/collector hook: lines 1099-1121
- filter update: line 1701
- map update: line 1717

The tap is reached only when the existing tap reports a pending first valid
capture. `ekfom_data.h_x` and `ekfom_data.h` are fully populated before line
1202. The signed `pd2` sidecar is copied from the already accepted
`corr_normvect` entries; it is not recomputed from points and normals.

| Formal object | Read-only source | Canonical helper | Access mode |
|---|---|---|---|
| measurement state | `state_ikfom &s` passed to `h_share_model` | `RuntimeEquivalenceAudit::checksumDoubles` over the existing explicit state field order | const read |
| full covariance | `kf.get_P()` | `RuntimeEquivalenceAudit::checksumDoubles` over 23×23 row-major native entries | const read |
| native Jacobian | `ekfom_data.h_x` | `RuntimeEquivalenceAudit::checksumMatrix` | const read |
| formal innovation | `ekfom_data.h` | `RuntimeEquivalenceAudit::checksumDoubles` | const read |
| signed geometric residual | existing `signed_geometric_residual_pd2` sidecar | `RuntimeEquivalenceAudit::checksumDoubles` | const read |
| accepted source indices | `readonly_tap_accepted_source_indices` populated during formal compression | `RuntimeEquivalenceAudit::checksumUInt64s` | const read |
| formal correspondence | accepted indices, saved formal plane parameters, and existing `Nearest_Points` entries | existing `ExactBytesChecksum` canonical field serialization | const read |
| map size | `ikdtree.validnum()` | integer comparison | const size query |

The checksum algorithm is `FNV1A64_EXACT_BYTES_V1`. The frozen helpers are in
`include/runtime_equivalence_audit.hpp` lines 144-152 and
`src/runtime_equivalence_audit.cpp` lines 470-518. No struct padding, address,
thread identifier, random value, unordered iteration, nearest-neighbor query,
or plane refit is used.

The exact execution order is:

1. formal correspondences, `h_x`, and `h` are complete;
2. all before checksums are computed;
3. `ReadonlyObservationTap::captureFirstValidMinimal` is called;
4. all after checksums are computed immediately;
5. `InCallImmutabilityAudit::record` receives only checksum integers, flags,
   and map-size integers;
6. the measurement callback returns to the existing filter path;
7. `kf.update_iterated_dyn_share_modified` performs the later filter update;
8. `map_incremental()` performs the later map update.

Therefore:

- `IN_CALL_HOOK_PLACEMENT_CONFIRMED=true`
- `COVARIANCE_IN_CALL_ACCESS_CONFIRMED=true`
- confidence: `CONFIRMED`
