# meituan-arrange-cli

本地 mock 的"美团安排"决策内核。输入一句自然语言诉求，输出可执行的 A/B 出行/吃喝安排。

技术栈：Python 标准库，零三方依赖。所有数据与外部调用均为本地 mock。

## 流水线

```
raw_goal ──▶ intent_parser ──▶ IntentFrame
                                   │
                                   ▼
                            scenario_router ──▶ ScenarioTemplate (family/friend/date/solo)
                                   │
                                   ▼
   LearnedSignals ──▶ planner.build_constraints ──▶ Constraint(hard/soft/risk, 带来源标签)
                                   │
                                   ▼
                       constraint_engine (filter_hard / score_soft + 动线权重 / apply_risk / rank)
                                   │
                                   ▼
                          generate_plans ──▶ Plan A / Plan B (含 route_minutes、per-slot geo)
                                   │
                          replanner (锁定其余 slot，局部替换，输出 diff)
                                   │
                          flywheel (会话末产出 delta + 商家信号，回写 LearnedSignals)
```

## 目录

- `models/` —— 数据契约（IntentFrame / ScenarioTemplate / Constraint / Plan / LearnedSignals / SessionState / RunRecord / 目录实体）
- `core/intent_ontology.py` —— 六维关键词规则表 + party 解析
- `core/intent_parser.py` —— 解析 raw_goal → IntentFrame（fired_rules 带 span）
- `core/scenario_router.py` —— 按 party 路由四模板
- `core/scenario_templates/` —— family / friend / date / solo 模板定义
- `core/constraint_engine.py` —— filter_hard / score_soft（含动线权重）/ apply_risk / rank
- `core/planner.py` —— build_constraints + generate_plans
- `core/replanner.py` —— 局部重规划 + diff
- `core/flywheel.py` —— LearnedSignals 读写与会话飞轮
- `scenarios/` —— 四场景对外封装
- `mock/repository.py` + `mock/data/*.json` —— 本地数据与 mock_geo_minutes

## 运行

```
python demo.py
```

`demo.py` 跑通验收四项：四句对照、solo 路由、动线权重开/关 rank 对照、两次会话学习注入。
