# Stage 1c pytest diagnosis

## 复现与定位

在 Stage 1c 修改前的 Stage 1b 基础 commit `2ef2dde` 上执行：

```bash
python3 -m pytest --collect-only -q
python3 -m pytest -vv --durations=50
```

共收集 150 项测试，第二条命令以 0 返回并在 31.69 秒内完成。因此本环境没有可复现的“原始卡住位置”，也没有可构造的最小卡住组合。逐文件二分和顺序组合定位不再有证据基础；把任意 figure、线程、子进程或 fixture 宣称为历史根因都会是臆测。

## 根本原因结论与修改

可证实结论是：当前 Stage 1b 基线不存在完整 pytest 卡住；历史现象可能已经在该 commit 前消失，或依赖另一运行环境。Stage 1b 已在 `pytest.ini` 保留 `faulthandler_timeout = 120`，Stage 1c 不删除、不跳过测试，也不以假 JSON 或输出字符串代替 return code。

Stage 1c 新增 `scripts/29_run_verified_pytest.py` 和 `src/eval/test_provenance.py`：每次由新 Python 进程真实执行 `python -m pytest -q`，设 900 秒上限，并仅以 `return_code == 0` 写入 `status = passed`。最终的两个 provenance 还必须与锁定 source hash、当前 test commit 和干净工作区一致。

由于没有复现顺序相关卡住，无法声称某项修复解释了顺序关系。新增测试只使用临时目录或只读仓库输入；线程池使用上下文管理器，现有绘图测试继续显式关闭 figure。

## 修改后完整测试

Stage 1c 实现后的开发前回归：

```text
python3 -m pytest -q
166 passed in 34.79s
```

诊断计时运行：

```text
python3 -m pytest -q --durations=10
166 passed in 32.08s
```

最慢 10 项为：

1. `tests/test_metrics.py::test_day8_summary_matches_recomputed_tum_errors` setup — 6.14 s
2. `tests/test_stage1b_pipeline_quick.py::test_stage1b_quick_pipeline_has_nine_sensor_runs_and_twenty_seven_trials` — 5.09 s
3. `tests/test_metric_redesign_stage1_pipeline.py::test_quick_pipeline_preserves_independent_sample_counts` — 4.53 s
4. `tests/test_observation_sweep_nested_retention.py::test_observation_retention_is_nested_with_fixed_final_point_count` — 2.13 s
5. `tests/test_day29_safe_figures.py::test_day29_generates_real_figures_and_safety_artifacts` — 1.69 s
6. `tests/test_within_sequence_validation_day18.py::test_day18_script_runs_and_preserves_prior_outputs` — 1.22 s
7. `tests/test_observation_simulator.py::test_sequence_observations_npz_contract_shapes` — 0.99 s
8. `tests/test_unbiased_probe_day17.py::test_day17_script_runs_and_preserves_day14_day15_day16_inputs` — 0.93 s
9. `tests/test_within_sequence_validation_day18.py::test_day18_script_reports_missing_day17_raw_trajectory` — 0.77 s
10. `tests/test_joint_risk_features_day21.py::test_day21_permutation_seed_is_fixed` — 0.58 s

最终锁定 commit 上的连续两次 verified pytest 结果与路径将在对应 machine-readable provenance 文件中记录；Engineering Gate 直接读取这些文件，不读取 Stage 1b 的手写状态 JSON。
