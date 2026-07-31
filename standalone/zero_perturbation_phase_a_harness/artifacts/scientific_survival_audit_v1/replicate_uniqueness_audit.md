# Replicate Uniqueness and Pseudoreplication Audit

The scientific replicate is one unique frozen `(source_checksum, target_checksum)` pair. Backend duplication does not increase this count.

| Condition | Cells | Effective min / median / max | Deterministic / partial / full | Authorized term |
|---|---:|---:|---:|---|
| INDEPENDENT_NOISE_FREE | 21 | 1 / 1 / 1 | 21 / 0 / 0 | `DETERMINISTIC_ZERO_INITIALIZATION_DISPLACEMENT` |
| SCAN_NOISE_ONLY | 21 | 10 / 10 / 10 | 0 / 0 / 21 | `REPEATABLE_SYSTEMATIC_OFFSET` |
| MAP_NOISE_ONLY | 21 | 10 / 10 / 10 | 0 / 0 / 21 | `REPEATABLE_SYSTEMATIC_OFFSET` |
| DROPOUT_ONLY | 21 | 10 / 10 / 10 | 0 / 0 / 21 | `REPEATABLE_SYSTEMATIC_OFFSET` |
| FULL_NOISE | 21 | 10 / 10 / 10 | 0 / 0 / 21 | `REPEATABLE_SYSTEMATIC_OFFSET` |

INDEPENDENT_NOISE_FREE repeats the same deterministic input pair ten times per cell; its near-zero execution dispersion cannot support a repeatable-systematic-bias claim. Noise and dropout signatures are reconstructed from the frozen arrays relative to each matching INDEPENDENT input; no snapshot is regenerated.
DROPOUT_ONLY masks are exact frozen-array subsequences. FULL_NOISE has `59` of 210 observations whose latent mask cannot be uniquely separated from scan noise, affecting `8` cells; those rows are explicitly marked as final-source proxies. `DROPOUT_MASK_IDENTITY_FULLY_RECONSTRUCTED = false` while `DROPOUT_INPUT_VARIATION_OBSERVED = true`.

## Long Corridor systematic-offset audit

| Condition | Backend | Geometry seed | Effective | Offset (m) | RMS (m) | Fraction | Direction concentration | FULL gate |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| FULL_NOISE | Open3D | 1334931069 | 10 | 0.00267963636 | 0.0011503064 | 0.98872505 | 0.978143555 | False |
| FULL_NOISE | Open3D | 1850310744 | 10 | 0.115628901 | 0.0112516207 | 0.999999884 | 0.999999889 | True |
| FULL_NOISE | Open3D | 1957656152 | 10 | 0.103894978 | 0.0418738731 | 0.999990722 | 0.999965421 | True |
| INDEPENDENT_NOISE_FREE | Open3D | 1334931069 | 1 | 0.0467578328 | 3.15724692e-16 | 1 | 1 | False |
| INDEPENDENT_NOISE_FREE | Open3D | 1850310744 | 1 | 0.11010281 | 8.04100622e-18 | 1 | 1 | False |
| INDEPENDENT_NOISE_FREE | Open3D | 1957656152 | 1 | 0.00705358784 | 4.21247392e-15 | 1 | 1 | False |
| FULL_NOISE | PCL | 1334931069 | 10 | 0.00361101861 | 0.00126220431 | 0.996522215 | 0.994168415 | False |
| FULL_NOISE | PCL | 1850310744 | 10 | 0.0994690029 | 0.00151227611 | 0.999999931 | 0.999999931 | True |
| FULL_NOISE | PCL | 1957656152 | 10 | 0.0202567149 | 0.00736880677 | 0.999951249 | 0.999959979 | True |
| INDEPENDENT_NOISE_FREE | PCL | 1334931069 | 1 | 0.00558080019 | 0 | 1 | 1 | False |
| INDEPENDENT_NOISE_FREE | PCL | 1850310744 | 1 | 0.099184864 | 0 | 1 | 1 | False |
| INDEPENDENT_NOISE_FREE | PCL | 1957656152 | 1 | 0.00899904227 | 0 | 1 | 1 | False |

- `SYSTEMATIC_OFFSET_FULL_NOISE_PASS = true`
- `SYSTEMATIC_OFFSET_CLAIM_SCOPE = LONG_CORRIDOR_FULL_NOISE`
- INDEPENDENT wording: `DETERMINISTIC_ZERO_INITIALIZATION_DISPLACEMENT`

Machine-readable details: `tables/replicate_uniqueness_by_cell.csv`, `tables/replicate_uniqueness_by_condition.csv`, `tables/measurement_seed_effectiveness.csv`, and `tables/repeat_index_effectiveness.csv`.
