# Day 16 Report - Unbiased toy_lio Protocol

## Direct Answers

- Day 16 是否修改了 legacy toy_lio 的默认复现行为？No. Default `run_toy_lio(...)` still uses `axis_bias_mode=legacy_scene_family`.
- legacy scene-family axis_bias 是否被保留为显式 legacy mode？Yes. `legacy_scene_family` preserves OC=0, CT=0.016, ST=0.022, RT=0.026.
- unbiased mode 中 applied_axis_bias 是否全部为 0？Yes.
- Day 16 能否证明 ODI 有效？No. Day 16 only establishes the unbiased protocol and does not test metric validity.
- Day 16 结果是否可以替代 Day 14 legacy biased toy_lio 作为主证据？No. It is a protocol and smoke execution check; Day 17-22 must provide unbiased metric validity.

## Summary

| sequence_id | scene_family | legacy_axis_bias | applied_axis_bias | final_axis_error | is_unbiased_protocol |
|---|---|---:|---:|---:|---|
| OC-L0-S01-M1 | OC | 0 | 0 | 2.74371459668e-05 | true |
| ST-L3-S01-M1 | ST | 0.022 | 0 | 0.0283213846711 | true |
| CT-L2-S01-M2 | CT | 0.016 | 0 | 9.1033888858e-05 | true |
| RT-L4-S01-M1 | RT | 0.026 | 0 | 0.0111792957362 | true |

## Protocol Status

- axis_bias_mode: `none`
- perturbation_profile: `unbiased_day16`
- legacy_behavior_preserved: `true`
- unbiased_protocol_passed: `true`

## Conclusion

Day 16 establishes an unbiased toy_lio protocol, but does not yet validate ODI.
Metric validity must be tested in Day 17-22.
