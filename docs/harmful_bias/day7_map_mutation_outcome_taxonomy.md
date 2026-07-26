# Day 7 Map-Mutation Outcome Taxonomy

Status: `DAY7_OUTCOME_TAXONOMY_PASS=true`

The taxonomy is derived from the current FAST-LIO2 and ikd-tree branches. It
does not introduce an estimator decision. Each emitted event uses exactly one
outcome below. `UNCLASSIFIED_FORMAL_PATH` is a fail-closed sentinel and is
never an acceptable runtime result.

## Candidate and delete-call outcomes

| Outcome | Existing formal branch |
| --- | --- |
| `INSERTED_NEW_VOXEL_REPRESENTATIVE` | Downsampling is enabled, the formal range result is empty, the candidate remains selected, and delete/add executes. |
| `REPLACED_EXISTING_VOXEL_REPRESENTATIVE` | Downsampling is enabled, one or more existing points are present, the candidate remains the strict closest-to-center point, and the formal delete/add executes. |
| `REINSERTED_EXISTING_VOXEL_REPRESENTATIVE` | More than one existing point is in the formal voxel result, an existing point is selected, and the formal delete/add consolidates the voxel around that selected existing point. |
| `REJECTED_EXISTING_REPRESENTATIVE_CLOSER` | Exactly one existing point is present, it is strictly closer to the voxel center, and the formal delete/add condition is false. |
| `ADDED_WITHOUT_DOWNSAMPLING` | `downsample_switch` is false and `Add_by_point` executes. |
| `DELETED_BY_BOX` | A public `Delete_Point_Boxes` element returns a positive logical delete count. |
| `DELETE_BOX_NO_MATCH` | A public `Delete_Point_Boxes` element returns zero. |

## Logger append outcomes

The six values correspond one-to-one with the existing `operation_set`.

- `LOGGER_APPEND_ADD_POINT`
- `LOGGER_APPEND_DELETE_POINT`
- `LOGGER_APPEND_DELETE_BOX`
- `LOGGER_APPEND_ADD_BOX`
- `LOGGER_APPEND_DOWNSAMPLE_DELETE`
- `LOGGER_APPEND_PUSH_DOWN`

## Logger apply outcomes

The six values correspond one-to-one with the existing `run_operation`
switch. They record the dispatch that was actually executed, without changing
its void return type.

- `REBUILD_LOG_ADD_POINT_APPLIED`
- `REBUILD_LOG_DELETE_POINT_APPLIED`
- `REBUILD_LOG_DELETE_BOX_APPLIED`
- `REBUILD_LOG_ADD_BOX_APPLIED`
- `REBUILD_LOG_DOWNSAMPLE_DELETE_APPLIED`
- `REBUILD_LOG_PUSH_DOWN_APPLIED`

## Rebuild commit outcome

- `REBUILD_COMMIT_REPLACED_SUBTREE`

## Fail-closed sentinel

- `UNCLASSIFIED_FORMAL_PATH`

The runtime Gate requires `unclassified_event_count=0`. Encountering the
sentinel sets `DAY7_EVENT_TRACE_SCHEMA_PASS=false`.

