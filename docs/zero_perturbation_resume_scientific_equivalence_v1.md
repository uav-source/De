# Phase A Fresh/Resumed Scientific Equivalence v1

This contract governs only the comparison of two already validated fixture execution rounds: one fresh run and one interruption/resume run. It does not alter whether an existing result may be accepted during resume. Existing results remain subject to exact schema, provenance, implementation, checksum, manifest, and SHA validation.

## Comparison classes

Thirty catalogued discrete fields use `EXACT` comparison. These include identity and provenance, solver status, failure classification, finite-state booleans, correspondence counts, PCL version and binary identity, exit/convergence/iteration status, and discrete normal counts. Any difference fails scientific equivalence.

Fourteen named continuous scalar fields use `NUMERIC_TOLERANCE`; the sixteen elements of `final_transform_4x4` use the same rule, giving thirty scalar comparison slots in the complete catalog. For finite values `a` and `b`, equivalence requires:

`abs(a - b) <= 1e-12 + 1e-12 * max(abs(a), abs(b))`

No rounding or storage-precision change is permitted. Two null values pass. A null/non-null pair fails `NULL_CONSISTENCY`.

Eight runtime-metadata categories are reported as `IGNORED_RUNTIME_METADATA`: runtime, timestamps, temporary path, process and thread IDs, execution order, and event timing. They cannot change a scientific decision. The frozen resume flow still requires 6 fresh results, 6 resumed results, 2 valid results skipped, and 0 valid results reexecuted.

For `failure_detail`, successful pairs must both be null and failed pairs must both contain nonempty strings. Text identity is reported but is non-decisive; `failure_classification` remains exact.

## Analysis and decision equivalence

Trial IDs, snapshot IDs, backend/failure inventories, classifications, input-pairing conclusions, Gate booleans, and final decisions must be exact. Continuous analysis summaries use the same numeric tolerance. Runtime-summary differences are reported but cannot affect scientific Gates.

The `1e-12` absolute tolerance is one billion times smaller than the `1e-3 m` translation Gate and approximately `1.745329252e8` times smaller than the `1.7453292519943296e-4 rad` rotation Gate. These constants were fixed before comparator implementation and are not fitted to the observed fixture difference.
