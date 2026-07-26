# Day 5 V5 clock-counter semantics adjudication

## Scope and source lock

This is a read-only adjudication of
`Degen-LIO-multihyp-D5-startup-sync-v5-audit.tar.gz`, SHA-256
`9ffba9f490153fe0d95c98b4f905816f499d673427b8e87255b268546a00349a`.
The archive's 461 `SHA256SUMS` entries passed before analysis. No ROS process,
bag replay, FAST-LIO2 process, detector, or real observation recomputation was
used.

The production source snapshots used here are:

- `repo/degen_overlay/src/fastlio2_adapter/tail_clock_protocol.py`, SHA-256
  `394f1ea0e088d55ac7247d55618ca9f0a67cb4190151a9771ff72d13cbf1cc7e`;
- `repo/degen_overlay/scripts/59_day5_tail_clock_node.py`, SHA-256
  `7b62eb0a21b69b135efadf107b4ebe5124e63b7ba90cac34a9c92a39a4c11493`.

## Symbol trace

| Source | Symbol | Lines | Counter/value | Bag update | Tail update | Used in final Gate | Finding |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| `tail_clock_protocol.py` | `TailClockState.note_bag_clock` | 150–161 | `clock_duplicate_count` | yes | no | yes | increments the shared counter when consecutive bag `/clock` values are equal |
| `tail_clock_protocol.py` | `TailClockState.note_bag_clock` | 150–161 | `clock_backward_count` | yes | no | yes | increments the shared counter when bag `/clock` moves backward |
| `tail_clock_protocol.py` | `TailClockState.note_publish` | 200–211 | `clock_duplicate_count` | no | yes | yes | increments the same shared counter if consecutive generated tail values are equal |
| `tail_clock_protocol.py` | `TailClockState.note_publish` | 200–211 | `clock_backward_count` | no | yes | yes | increments the same shared counter if generated tail values move backward |
| `tail_clock_protocol.py` | `tail_clock_ns` | 86–91 | tail value | no | yes | no | returns `start + published_index × step` after rejecting non-positive steps |
| `tail_clock_protocol.py` | `TailClockState.finish` | 221–235 | `handoff_pass` | no | no | yes | requires the phase-mixed duplicate/backward counters and overlap counter all to be zero |
| `59_day5_tail_clock_node.py` | `TailClockNode.clock_callback` | 135–145 | bag clock | yes | no | no | calls `note_bag_clock` while tail publication is inactive |
| `59_day5_tail_clock_node.py` | `TailClockNode.publish_loop` | 220–268 | tail value | no | yes | no | calls `tail_clock_ns`, records the value, and increments `index` by one |

Therefore:

`clock_duplicate_count = bag-phase duplicates + tail-phase duplicates`

`MIXED_CLOCK_COUNTER_CONFIRMED=true`

The recorded value `clock_duplicate_count=226` is a bag-or-mixed counter. It
must not be renamed or interpreted as `tail_clock_duplicate_count`.

## Independent tail-clock calculation

Frozen values:

- `last_bag_clock_ns=1600270417569223231`
- `tail_clock_step_ns=1000000`
- `tail_first_clock_ns=1600270417570223231`
- `tail_publish_count=10383`
- `tail_final_clock_ns=1600270427952223231`
- `clock_backward_count=0`
- `clock_publisher_overlap_count=0`

Independent results:

- expected first:
  `1600270417569223231 + 1000000 = 1600270417570223231`;
- first difference: `0 ns`;
- expected final:
  `1600270417570223231 + (10383 - 1) × 1000000 =
  1600270427952223231`;
- final difference: `0 ns`.

The locked positive-step affine rule, sequential index, and matching boundary
values imply:

- `tail_clock_duplicate_count_derived=0`;
- `tail_clock_backward_count_derived=0`;
- derivation basis:
  `DERIVED_FROM_LOCKED_GENERATION_RULE_AND_BOUNDARY_VALUES`.

This is a source-and-boundary proof. It is not a claim that all 10,383 tail
messages were individually logged and inspected.

The mixed total is 226 and the derived tail contribution is zero, so the
bag-phase duplicate observation is 226 with provenance
`MIXED_TOTAL_MINUS_DERIVED_TAIL_ZERO`.

## Gate defect and correction boundary

`finish()` rejected the handoff because its zero-duplicate check consumed the
phase-mixed accumulator. The original formal classification
`TAIL_CLOCK_DUPLICATE_TIME` is therefore invalid for the executed tail phase.
Its invalidation reason is
`MIXED_BAG_AND_TAIL_CLOCK_DUPLICATE_COUNTER`.

This correction applies only to `avia_quick_shack/AUDIT_ONLY_R1`. It does not
turn the six-run V5 matrix into a pass and does not prove cross-process
repeatability.
