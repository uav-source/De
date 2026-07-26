# Day 7 Map-Update Source-Path Resolution

Status: `DAY7_SOURCE_PATH_RESOLUTION_PASS=true`

This audit resolves the code that is present before Day 7 instrumentation. The
FAST-LIO2 checkout is `spike/readonly-observation-tap-v1` at
`f19b4c42a77dc11793c912d67b9e56dcafa279dc`. The ikd-tree submodule is detached
at `e2e3f4e9d3b95a9e66b1ba83dc98d4a05ed8a3c4` and contains the already
authorized coherent-snapshot changes.

## Resolved paths

| Operation | Source file | Symbol and line range | Source SHA-256 | Formal input and output | Branch conditions | Locks and rebuild/logger behavior | Safe diagnostic hook | Confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Scan-local map eviction | `src/laserMapping.cpp` | `lasermap_fov_segment`, 516–562 | `4ea682c9aa4248489979cfd05ac9e4b7e2caf87ff0020fe5ad210a756e065b69` | Input: shifted local-map boxes. Output: deleted logical-point count. | Calls `Delete_Point_Boxes` only when `cub_needrm` is nonempty. | No caller-held ikd-tree lock. The public delete API selects direct or rebuild-aware handling. | Before/after the existing call; pass its existing box vector without recomputing boxes. | CONFIRMED |
| Mapping insertion batch construction | `src/laserMapping.cpp` | `map_incremental`, 712–759 | `4ea682c9aa4248489979cfd05ac9e4b7e2caf87ff0020fe5ad210a756e065b69` | Input: transformed feature points and the already-computed `Nearest_Points`. Output: ordered downsample and no-downsample batches. | Existing center-distance loop chooses whether each point enters either batch. | No map mutation occurs until the two public calls at lines 755–756. | Mark the two existing calls separately and preserve their order and boolean `downsample_on` values. | CONFIRMED |
| Public point insertion | `include/ikd-Tree/ikd_Tree.cpp` | `KD_TREE::Add_Points`, 480–581 | `4a89359680234d0ee0da99076fd4facb74316a11601f431070f1a8850802f471` | Input: ordered point vector and `downsample_on`. Output: `tmp_counter`. | `downsample_on && DOWNSAMPLE_SWITCH`; formal box/center calculation; `Search_by_range`; strict `<` representative selection; mutation only when storage size is greater than one or the candidate remains selected. | Direct path calls `Delete_by_range`/`Add_by_point`. Rebuild-root path holds `working_flag_mutex`; when `rebuild_flag` is true it appends delete then add while holding `rebuild_logger_mutex_lock`. | Observe existing candidate, box, center, `Downsample_Storage`, selected point, taken branch, and logger append sites. | CONFIRMED |
| Recursive point insertion | `include/ikd-Tree/ikd_Tree.cpp` | `KD_TREE::Add_by_point`, 1148–1212 | `4a89359680234d0ee0da99076fd4facb74316a11601f431070f1a8850802f471` | Input: root link, point, rebuild permission, parent axis. Output: one inserted node. | Null link creates a node; otherwise existing split-axis comparison chooses left or right. | When the selected child is `Rebuild_Ptr`, the existing order is `working_flag_mutex`, recursive insert, optional `rebuild_logger_mutex_lock` append, unlock logger, unlock working. | Record the existing append immediately adjacent to `Rebuild_Logger.push`; do not add a second search or alter recursion. | CONFIRMED |
| Public box deletion | `include/ikd-Tree/ikd_Tree.cpp` | `KD_TREE::Delete_Point_Boxes`, 646–678 | `4a89359680234d0ee0da99076fd4facb74316a11601f431070f1a8850802f471` | Input: ordered box vector. Output: summed deleted valid-point count. | Each box selects direct or rebuild-root handling. | Rebuild-root path holds `working_flag_mutex`, performs deletion, then optionally appends under `rebuild_logger_mutex_lock`. | Observe each existing box and returned delta; record the existing append in place. | CONFIRMED |
| Recursive range deletion | `include/ikd-Tree/ikd_Tree.cpp` | `KD_TREE::Delete_by_range`, 920–1004 | `4a89359680234d0ee0da99076fd4facb74316a11601f431070f1a8850802f471` | Input: root link, formal box, rebuild permission, downsample flag. Output: deleted valid-point count. | Null/deleted tree, three non-overlap exits, full-subtree cover, current-point cover, then left/right recursion. | A recursion edge equal to `Rebuild_Ptr` uses the existing working/logger lock order and appends `DELETE_BOX` or `DOWNSAMPLE_DELETE`. | Record only values and control-flow exits already present; never issue another range search. | CONFIRMED |
| Recursive point deletion | `include/ikd-Tree/ikd_Tree.cpp` | `KD_TREE::Delete_by_point`, 1007–1072 | `4a89359680234d0ee0da99076fd4facb74316a11601f431070f1a8850802f471` | Input: root link and point. Output: void, with logical delete when an undeleted exact point is reached. | Null/deleted exit, exact-point delete, or split-axis recursion. | Rebuild-child recursion preserves the existing working/logger lock order and appends `DELETE_POINT`. | Logger append observation only; Day 7 production calls do not introduce new point deletes. | CONFIRMED |
| Range restoration | `include/ikd-Tree/ikd_Tree.cpp` | `KD_TREE::Add_by_range`, 1075–1145 | `4a89359680234d0ee0da99076fd4facb74316a11601f431070f1a8850802f471` | Input: root link and box. Output: restored logical flags. | Null/non-overlap/full-cover/current-point and recursive branches. | Rebuild-child recursion appends `ADD_BOX` under the existing lock order. | Logger append/apply taxonomy only; no new invocation. | CONFIRMED |
| Rebuild logger apply | `include/ikd-Tree/ikd_Tree.cpp` | `KD_TREE::multi_thread_rebuild`, 230–369; `run_operation`, 372–408 | `4a89359680234d0ee0da99076fd4facb74316a11601f431070f1a8850802f471` | Input: FIFO `Operation_Logger_Type`. Output: operation applied to the rebuilt subtree in queue order. | The loop pops until empty; `run_operation` dispatches the six existing enum values. | Apply order is fixed by `front`, `pop`, unlock, `run_operation`, and relock. The commit replaces the selected child after logger drain. | Assign diagnostic sequence at append, carry it in the existing logger value copy, and record immediately around pop/apply/commit without changing order. | CONFIRMED |
| Rebuild selection and commit | `include/ikd-Tree/ikd_Tree.cpp` | `KD_TREE::Rebuild`, 889–917; `multi_thread_rebuild`, 230–369 | `4a89359680234d0ee0da99076fd4facb74316a11601f431070f1a8850802f471` | Input: subtree selected by existing size/criterion logic. Output: rebuilt subtree installed in the same parent link. | Trees of at least 1500 points may update `Rebuild_Ptr`; smaller trees rebuild synchronously. | Existing lock order is rebuild-pointer then working; search exclusion and logger locks remain unchanged. | Record generation, logical counts, logger summaries, and commit checksum at the existing commit boundary. | CONFIRMED |
| Coherent map identity source | `src/laserMapping.cpp` | `experimentAMapSnapshotCoherentImpl`, 1937–2007 | `4ea682c9aa4248489979cfd05ac9e4b7e2caf87ff0020fe5ad210a756e065b69` | Input: the existing coherent copied point vector. Output: existing `CoherentMapSnapshotV2`. | Existing snapshot Gate and digest logic remain unchanged. | `Snapshot_Valid_Points_Coherent` already uses rebuild-pointer then working lock and releases both before digesting. | Reuse the already-copied point vector after the formal coherent copy; do not call the map a second time. | CONFIRMED |

## Formal downsample decision

The formal voxel identity is the six box bounds calculated at lines 499–504.
Day 7 may serialize those exact local values. It must not recompute a voxel
using a parallel formula.

`Downsample_Storage` is the exact formal range-search result. The candidate is
initialized as the selected representative. Existing points replace it only
on strict `tmp_dist < min_dist`; equal distance does not replace the current
selection. The decision context therefore consists only of this existing
vector and the strict comparison results already consumed by the formal loop.

## Lock and perturbation boundary

Instrumentation may add bounded buffer writes, canonical point hashing, fixed
diagnostic sequence atomics, and observations adjacent to existing logger
append/apply sites. It may not introduce a map-path mutex, change the order or
extent of any existing lock, add searches, or control any formal condition.

`INSTRUMENTATION_TIMING_PERTURBATION_PRESENT=true`.

