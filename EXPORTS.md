# EXPORTS —— 对外 import 清单（供 Codex 侧导入）

所有数据契约类的**定义真源**在 `models/` 包内，并已从下方"导入路径"列出的 `core.*`
模块再导出（re-export），两种路径均可用：

```python
# 既可从 models 直接导入
from models import IntentFrame, ScenarioTemplate, Plan, Constraint, LearnedSignals
# 也可从契约约定的 core 路径导入（已 re-export）
from core.intent_ontology import IntentFrame
from core.scenario_templates import ScenarioTemplate
from core.planner import Plan, PlanSlot
from core.constraint_engine import Constraint, HardConstraint, RiskRule
from core.flywheel import LearnedSignals, SessionState, RunRecord
```

类型标注约定：`str/int/float/bool/list/dict` 为 Python 内置；`Optional[X]` 表示可空。
"必选" = 构造时必须显式提供（无默认值）。

---

## IntentFrame
- **导入路径**：`from core.intent_ontology import IntentFrame`（真源 `models/intent.py`）
- **用途**：一句诉求解析后的结构化意图。

| 字段 | 类型 | 必选 | 说明 |
|---|---|---|---|
| raw_goal | str | 是 | 原始诉求文本 |
| vibe | Optional[str] | 否 | 松弛/热闹/文艺/出片 |
| setting | Optional[str] | 否 | 室内/室外/商场/公园 |
| effort | Optional[str] | 否 | 躺平/轻度/能折腾 |
| spend | Optional[str] | 否 | 省/适中/不在乎 |
| meal_focus | Optional[str] | 否 | 正餐/小吃/咖啡/不重要 |
| duration_hint | Optional[str] | 否 | 短/半天/全天 |
| sensitivities | list[str] | 否 | 减脂/忌辣/孩子友好/低强度 |
| party | list[str] | 否 | 角色列表，如 ["user"], ["user","kid"] |
| fired_rules | list[tuple[str, tuple[int,int]]] | 否 | (规则名, (start,end)) 命中 span |

- **方法**：`summary() -> str` 单行可读摘要。

---

## ScenarioTemplate
- **导入路径**：`from core.scenario_templates import ScenarioTemplate`（真源 `models/scenario.py`）
- **构建**：`from core.scenario_templates import build, all_ids`；`build("solo") -> ScenarioTemplate`，`all_ids() -> ["family","friend","date","solo"]`。

| 字段 | 类型 | 必选 | 说明 |
|---|---|---|---|
| id | str | 是 | family/friend/date/solo |
| label | str | 是 | 中文名 |
| base_constraints | list[HardConstraint] | 否 | 场景硬约束基线 |
| weight_overrides | dict[str, float] | 否 | field → 软权重 |
| risk_extras | list[RiskRule] | 否 | 场景风险增项 |

---

## Plan / PlanSlot
- **导入路径**：`from core.planner import Plan, PlanSlot`（真源 `models/plan.py`）
- **生产**：`core.planner.generate_plans(...) -> list[Plan]`；排序由 `core.constraint_engine.rank(plans, use_route_weight=True)` 完成，并写入 `score`。

### Plan
| 字段 | 类型 | 必选 | 说明 |
|---|---|---|---|
| plan_id | str | 否 | 稳定标识（默认等于 id） |
| title | str | 否 | 可读标题 |
| route_minutes | int | 否 | 总通勤分钟（新增字段） |
| slots | list[PlanSlot] | 否 | 时段列表 |
| locked_items | list[str] | 否 | 锁定的 slot_id（重规划时其余锁定） |
| flexible_items | list[str] | 否 | 可替换的 slot_id（默认全部 slot） |
| score | float | 否 | 对外评分（镜像 total_score） |
| rejected_merchants | list[str] | 否 | 兜底/资源校验淘汰的 merchant_id |
| id | str | 是 | 内部唯一 id |
| scenario_id | str | 是 | 所属场景 |
| soft_score / risk_penalty / total_score | float | 否 | 评分中间量 |
| notes | list[str] | 否 | 备注 |

- **方法**：`geo_path() -> list[str]`；`summary() -> str`。

### PlanSlot
| 字段 | 类型 | 必选 | 说明 |
|---|---|---|---|
| slot_id | str | 否 | 稳定标识（默认等于 ref_id） |
| name | str | 是 | 展示名 |
| geo | str | 是 | zone 字符串（新增字段） |
| window | str | 否 | 时间窗 "HH:MM-HH:MM" |
| kind | str | 是 | activity/meal |
| ref_id | str | 是 | 对应 activity/restaurant id |
| duration_min | int | 否 | 时长 |
| groupbuy_id | Optional[str] | 否 | 命中的团购券 id |
| groupbuy_save | float | 否 | 团购节省金额 |

---

## 约束类（Constraint / HardConstraint / RiskRule / SoftPref / ConstraintItem / RiskItem）
- **导入路径**：`from core.constraint_engine import Constraint, HardConstraint, RiskRule, SoftPref`
  （真源 `models/constraint.py` 与 `models/scenario.py`）
- **生产**：`core.planner.build_constraints(intent, scenario, signals, profile) -> Constraint`。

### Constraint（带来源标签的三类约束容器）
| 字段 | 类型 | 说明 |
|---|---|---|
| hard | list[ConstraintItem] | 硬约束（含 source/reason） |
| soft | list[SoftPref] | 软偏好（含 source/reason/target） |
| risk | list[RiskItem] | 风险规则（含 source/reason） |

- **方法**：
  - `hard_rules() -> list[HardConstraint]`
  - `soft_weights() -> dict[str,float]`（同字段多来源叠加）
  - `risk_rules() -> list[RiskRule]`
  - `source_breakdown() -> dict[str,int]`（按 本次目标/家庭档案/历史学习 计数）
- **来源常量**：`from models import SOURCE_GOAL, SOURCE_PROFILE, SOURCE_LEARNED`
  （值为 "本次目标"/"家庭档案"/"历史学习"）

### HardConstraint
字段 `field:str, op:str, value:object=None, label:str=""`；方法 `describe()->str`。
op ∈ {true,false,eq,ne,in,contains}。

### RiskRule
字段 `name:str, field:str, op:str, value:object=None, penalty:float=1.0, label:str=""`；
方法 `describe()->str`。op ∈ {true,false,eq,ne,gt}。

### SoftPref
字段 `field:str, weight:float, source:str, reason:str, target:object=None`。

### 评估 API（约束求值入口，位于 `core.constraint_engine`）
- `filter_hard(candidates, hard_rules) -> list` 硬过滤。
- `score_soft(candidate, soft_prefs) -> float` 单候选软评分。
- `apply_risk(candidates, risk_rules) -> float` 风险扣分累加。
- `rank(plans, use_route_weight=True) -> list[Plan]` 含动线权重的排序；写入 `total_score`/`score`。
- `mock_geo_minutes(geo_a, geo_b) -> int`（位于 `mock.repository`）动线近似分钟。

---

## LearnedSignals
- **导入路径**：`from core.flywheel import LearnedSignals`（真源 `models/signals.py`）
- **读写**：`from core.flywheel import Flywheel`；`Flywheel(path?).load() -> LearnedSignals`、
  `.save(signals)`、`.emit(...) -> (LearnedSignals, RunRecord)`。
- **持久化路径**：默认 `mock/data/learned_signals.json`（`mock.repository.LEARNED_SIGNALS_PATH`）。

| 字段 | 类型 | 必选 | 说明 |
|---|---|---|---|
| user_pref_deltas | dict[str,float] | 否 | field → 软权重增量 |
| merchant_signals | dict[str,float] | 否 | merchant_id → 偏好增量 |
| scenario_overrides | dict[str,dict] | 否 | scenario_id → {field: delta} |
| last_updated | str | 否 | ISO 时间戳 |

- **方法**：`to_dict()->dict`、`from_dict(d)->LearnedSignals`（classmethod）、`is_empty()->bool`。

---

## SessionState
- **导入路径**：`from core.flywheel import SessionState`（真源 `models/session.py`，
  经 flywheel 再导出；会话管理后续若独立成模块，导入路径保持不变）。

| 字段 | 类型 | 必选 | 说明 |
|---|---|---|---|
| current_intent | Optional[IntentFrame] | 否 | 当前意图 |
| current_plan | Optional[Plan] | 否 | 当前方案 |
| current_exec_state | str | 否 | idle/planned/replanned/done |
| scenario_id | Optional[str] | 否 | 当前场景 |
| signals_snapshot | Optional[LearnedSignals] | 否 | 开局注入的信号快照 |
| candidate_plans | list[Plan] | 否 | 候选方案集合 |

---

## RunRecord
- **导入路径**：`from core.flywheel import RunRecord`（真源 `models/record.py`）
- **生产**：`Flywheel.emit(...)` 返回的第二个值。

| 字段 | 类型 | 必选 | 说明 |
|---|---|---|---|
| id | str | 是 | 运行 id |
| ts | str | 否 | ISO 时间戳 |
| intent | Optional[IntentFrame] | 否 | 本次意图 |
| chosen_plan_id | Optional[str] | 否 | 选中方案 id |
| feedback | Optional[str] | 否 | like/dislike 等 |
| replanned | bool | 否 | 是否发生重规划，默认 False |
| signals_emitted | list[str] | 否 | 本次产出的信号描述 |
| **fallback_triggered** | bool | 否 | **新增字段**，是否系统兜底触发，默认 **False** |

---

## Flywheel.emit 签名
```python
Flywheel.emit(
    signals: LearnedSignals,
    intent: IntentFrame,
    scenario_id: str,
    chosen_plan: Optional[Plan],
    feedback: str = "like",
    replanned: bool = False,
    fallback_triggered: bool = False,   # True 时对 rejected_merchants 施加负信号 + 场景韧性增量
    persist: bool = True,
) -> tuple[LearnedSignals, RunRecord]
```

## replanner.replan 签名
```python
core.replanner.replan(
    plan, slot_index, constraint,
    signals=None, profile=None, repo=None,
    fallback_triggered: bool = False,   # True 时写入 new_plan.rejected_merchants
    exclude_ids=None,
) -> tuple[Optional[Plan], Optional[ReplanDiff]]
```
`ReplanDiff` 字段：`slot_index, field_from, field_to, locked, fallback_triggered,
delta_route_minutes, delta_total`；方法 `describe()->str`。
