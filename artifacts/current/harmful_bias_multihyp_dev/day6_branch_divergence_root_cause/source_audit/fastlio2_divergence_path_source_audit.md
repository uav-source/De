# FAST-LIO2 divergence-path static audit

This is a static engineering audit. Parallel code is not direct evidence of a data race.

The frozen record localizes the first visible difference to formal measurement/correspondence objects while the prior remains equal. It does not include map-content, insertion-order, scheduling, thread, neighbor-identity, plane-array, or raw-payload traces.

## Bounded findings

- `h_share_model` contains a parallel per-source correspondence-search loop with index-owned writes, followed by serial effective-point compaction and formal J/h construction.
- `Nearest_Search`, plane fitting, incremental insertion/deletion, and the iterated state/covariance update are upstream or downstream static paths.
- The available runtime record directly supports formal measurement divergence and subsequent state propagation.
- Map, scheduling, ikd-tree ordering, and a conflicting shared write remain unobserved.

## Symbol table

- `src/laserMapping.cpp::h_share_model` lines `923-1123`: `PLAUSIBLE_BUT_UNPROVEN`.
- `src/laserMapping.cpp::formal_correspondence_and_jacobian_construction` lines `1005-1205`: `DIRECTLY_SUPPORTED`.
- `src/laserMapping.cpp::map_incremental` lines `712-762`: `NOT_OBSERVABLE`.
- `include/common_lib.h::esti_plane` lines `226-255`: `PLAUSIBLE_BUT_UNPROVEN`.
- `include/ikd-Tree/ikd_Tree.cpp::Nearest_Search` lines `426-463`: `NOT_OBSERVABLE`.
- `include/ikd-Tree/ikd_Tree.cpp::Add_Points` lines `478-631`: `NOT_OBSERVABLE`.
- `include/ikd-Tree/ikd_Tree.cpp::Delete_Point_Boxes` lines `632-832`: `NOT_OBSERVABLE`.
- `include/IKFoM_toolkit/esekfom/esekfom.hpp::update_iterated_dyn_share_modified` lines `1619-1932`: `DIRECTLY_SUPPORTED`.
