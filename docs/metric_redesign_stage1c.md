# Metric Redesign Stage 1c：独立确认性验证

Stage 1c 是在 Stage 1 和 Stage 1b 之上的增量确认阶段。它冻结已有指标定义，修复过程噪声配对与低信息阈值的复现缺口，并用与开发集完全隔离的 geometry、sensor 和 process seeds 做一次确认性检验。它不是估计器实现。

## 为什么需要 Stage 1c

Stage 1b 的最终结论仍是 `STAGE1B_NO_GO`：工程和机制检查通过，但主风险指标的 Prediction Gate 失败；geometry test 的等级内残差相关性为负，低信息比例与最长低信息持续时间又因固定阈值而退化为常数。Stage 1b 的 `404`、`505` 已参与其开发/测试流程，因此二者不能再次冒充独立确认样本。

Stage 1c 为 test 预留 8 个全新 geometry blocks：`606, 707, 808, 909, 1011, 1213, 1417, 1619`。以 geometry seed 作为最外层 bootstrap block，可在同一个场景结构下共同重采样两个 sensor runs 和四个退化等级；8 个 blocks 也使 7/8 的机制与方向一致性规则可被直接审计。

## 随机性与配对单元

Stage 1b 的过程噪声 seed 只由 process seed 和 motion profile 等较少字段决定，因此相同噪声会跨 geometry、sensor 和 experiment family 过度复用。Stage 1c 的解析 seed 由以下冻结单元派生：

```text
(experiment_family, geometry_seed, sensor_seed, process_seed, motion_profile_id)
```

退化 level 不进入派生式，所以同一单元在各 level 之间严格配对；family、geometry 或 sensor 改变时则得到独立噪声。审计同时检查解析 seed 与实际噪声 checksum。Development 预期 900 条独立序列，test 预期 1440 条。

Development 使用 sensor seeds `11, 22` 和 process seeds `1001..1030`；test 使用 `33, 44` 和 `2001..2030`。这与 geometry seed 的隔离共同避免开发时观察到的传感器/过程随机性泄漏进确认集。

## 冻结指标与低信息阈值

主退化检测指标固定为 `ODI_trans`，因为它回答“退化程度及弱方向是否被检测到”。主风险暴露指标仍为 `mean_inverse_axis_information`，因为它直接累积弱轴信息不足并用于预测 `mean_final_axis_error_squared`；两者承担不同问题，不能互相替代。

低信息阈值 `tau_I` 只从 development Open Control 的 `axis_information_normalized` frame values 的 5% 分位数计算。`analysis_lock.json` 冻结该阈值、epsilon、指标/目标、预期方向、开发与保留 seeds、源码/配置/指标/统计代码哈希以及 development 数据和表格哈希。Test 只读取锁定阈值；缺锁、脏工作区、未提交 lock、源码或配置哈希变化、seed 变化、或 pytest provenance 不匹配都会以 `REFUSE_TEST_EXECUTION` 拒绝运行。这样 test 结果出现后无法通过改阈值或分析代码来追求更好的结论。

## Gate 与授权边界

最终分别报告 Engineering、Mechanism、Detector 和 Prediction Gate：

- Detector Gate 检验两个 sweep 中 `ODI_trans` 对严重度的相关、逐 geometry 单调性、配对单调率、弱方向对齐和 Open Control 误触发率。
- Prediction Gate 检验 `mean_inverse_axis_information` 对最终弱轴误差平方的预测，并检查使用 development 等级中位数中心化后的 test 等级内残差没有明显反向。
- `WEAK_UPDATE_AUTHORIZED` 只要求 Engineering、Mechanism、Detector 全部通过。退化检测可靠即可授权下一阶段的受控弱子空间更新研究，不要求当前风险预警已经可靠。
- `RISK_WARNING_AUTHORIZED` 额外要求两个 sweep 的 Prediction Gate 全部通过。

因此允许出现 weak update 授权为真、risk warning 授权为假的结果。无论 Gate 通过与否，Stage 1c 都不实现 weak-subspace update、不接入 FAST-LIO2，也不构成正式 Degen-LIO。

## 版本与 pytest 证据

每个 manifest 分别保留数据生成 commit/source hash、分析历史中的 commit/source hash，以及 test execution commit/source hash；分析 lock 的文件 SHA-256 和最近记录该 lock 的 commit 也单独保存。`--analyze-only` 只能在同一锁定源码和有效 provenance 下追加新的 analysis record，不改写数据生成记录。

`scripts/29_run_verified_pytest.py` 从新的 Python 进程调用 `[sys.executable, "-m", "pytest", "-q"]`。它只按真实 return code 判定成功，并记录输出哈希、测试计数、Git 状态、source hash、Python/pytest/platform/hostname。最终 test 前必须连续生成两个 return code 为 0、工作区干净、commit 与 source hash 都匹配的 provenance 文件；第二次运行固定 `PYTHONHASHSEED=0`。

## 运行顺序

```bash
python3 -m pytest -q
python3 scripts/28_run_metric_redesign_stage1c.py --quick --run-id stage1c_quick_v1
python3 scripts/28_run_metric_redesign_stage1c.py --development --run-id stage1c_dev_v1 --workers 8 --resume
python3 scripts/28_run_metric_redesign_stage1c.py --lock-analysis --development-run-dir results/metric_redesign_stage1c/development/stage1c_dev_v1
python3 -m pytest -q
git commit -m "feat: lock stage1c confirmatory analysis"
git status --porcelain
python3 scripts/29_run_verified_pytest.py --output results/metric_redesign_stage1c/test_provenance_run1.json
PYTHONHASHSEED=0 python3 scripts/29_run_verified_pytest.py --output results/metric_redesign_stage1c/test_provenance_run2.json
python3 scripts/28_run_metric_redesign_stage1c.py --test --run-id stage1c_test_v1 --analysis-lock results/metric_redesign_stage1c/development/stage1c_dev_v1/analysis_lock.json --workers 8 --resume
python3 scripts/28_run_metric_redesign_stage1c.py --analyze-only --run-dir results/metric_redesign_stage1c/test/stage1c_test_v1
```

脚本默认拒绝覆盖已有 run。`--resume` 只恢复指定 run；`--overwrite` 只显式重建指定 run，二者不能同时使用。

## PASS / NO-GO 规则

Engineering 必须满足两次真实 pytest、版本/哈希/目录/数量/轨迹/噪声/非 GT 泄漏和低信息指标检查。Mechanism 必须满足 sweep 结构不变量，并各有至少 7/8 geometry blocks 呈现严格轴向信息次序。Detector 必须在两个 sweep 均达到冻结阈值且 Open Control 误触发率不超过 0.10。Prediction 两个 sweep 都通过为 `PREDICTION_PASS`，仅一个为 `PREDICTION_PARTIAL`，否则为 `PREDICTION_FAIL`。

任何失败都按冻结规则如实报告，不查看 test 后调参或换指标重跑。授权结论严格由上述布尔关系生成。
