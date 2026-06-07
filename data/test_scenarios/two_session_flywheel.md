# 两次会话飞轮验证脚本

供 Codex 端按此执行并核对。所有数据为本地 mock，结果可复现（开始前清空持久化）。

## 前置
- 持久化路径：`mock/data/learned_signals.json`（信号）、`mock/data/runs.jsonl`（留痕）。
- 执行前删除上述两文件，确保第一次会话从空白信号起步。
- Profile：`home_geo="central"`，单人（party=[user]）。

## 会话流水线
```
intent_parser.parse(goal, profile)
  → scenario_router.route(intent, profile)            # solo
  → planner.build_constraints(intent, scenario, signals, profile)
  → planner.select_ab(rank(generate_plans(...), use_route_weight=True))  # A/B
  → flywheel.emit(signals, intent, scenario_id, chosen_plan, feedback)   # 会话末
```

## 第一次会话
- 输入 goal：`一个人放松随便逛逛喝咖啡`
- 开局信号：空（`LearnedSignals.is_empty() == True`）
- 产出 A 方案：`solo:act_cinema+res_noodle`
  影院观影@central → 街角面馆@central ｜ route=10min ｜ total=6.40
- 用户反馈：对 A 方案 **dislike**（街角面馆不合口味）
- 会话末 emit 产出信号（写入 learned_signals.json）：
  - `user_pref_deltas = {"meal_focus": -0.2, "vibe": -0.2}`
  - `merchant_signals = {"act_cinema": -0.5, "res_noodle": -0.5}`   ← 商家被降权
  - `scenario_overrides["solo"] = {"solo_pref": -0.2, "meal_focus": -0.4, "vibe": -0.4}`
  - `runs.jsonl` 追加一条 RunRecord（feedback=dislike，fallback_triggered=False）

## 第二次会话
- 输入 goal：与第一次相同 `一个人放松随便逛逛喝咖啡`
- 开局信号：flywheel 自动 `load()`，`is_empty() == False`，加载上一轮信号
- build_constraints 注入历史学习项（场景优先覆盖 + 全局让位），评分受 `res_noodle` 负信号影响
- 产出 A 方案：`solo:act_cinema+res_dimsum`
  影院观影@central → **粤式点心@central** ｜ route=10min ｜ total=4.70

## 预期可识别差异
| 维度 | 第一次会话 | 第二次会话 | 结论 |
|---|---|---|---|
| A 方案餐饮 slot | 街角面馆 `res_noodle` | 粤式点心 `res_dimsum` | 被降权商户从首选剔除 |
| `res_noodle` 商家信号 | 0（无） | −0.5 | 商户降权可观察 |
| A 方案总分 | 6.40 | 4.70 | dislike 后整体分值回落 |
| 开局信号 | empty | 非空（注入上轮） | 飞轮自动加载并生效 |

核对要点：第二次会话 A 方案中 **`res_noodle` 不再出现**，被 `res_dimsum` 取代；
`merchant_signals["res_noodle"] == -0.5`；第二次 `build_constraints` 的 soft 列表中
含 `source==历史学习` 的条目。

## 参考断言（伪代码）
```python
assert s1_is_empty
assert "res_noodle" in [s.ref_id for s in plan_s1_A.slots]
assert signals.merchant_signals["res_noodle"] == -0.5
assert not s2_is_empty
assert "res_noodle" not in [s.ref_id for s in plan_s2_A.slots]
assert "res_dimsum" in [s.ref_id for s in plan_s2_A.slots]
```
对应自动化用例：`tests/test_acceptance.py::test_two_session_observable_plan_diff`。
