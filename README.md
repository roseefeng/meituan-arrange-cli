# 美团安排 · meituan-arrange-cli

美团黑客松参赛作品,赛道：本地探索 · 周末闲时活动规划。
"美团安排"是本地短时活动的「规划 + 执行」Agent：一句话目标进，输出可执行方案，自动完成关键下单 / 预约 / 配送。

## 安装与运行

依赖项为 Python 标准库，零第三方依赖（Python 3.10+）。唯一入口 `cli/main.py`。

```bash
python cli/main.py plan "今天下午想带老婆孩子出去玩几小时，别离家太远"
```

- 加 `--verbose` 查看完整推理链（意图解析、候选数量、评分与风险扣分、tool I/O、信号注入与产出）。
- 加 `--scenario family|friend|date|solo` 指定场景（默认 `family`）。

```bash
python cli/main.py plan "周末和三五好友找个地方热闹一下" --scenario friend --verbose
```

<<<<<<< HEAD
## 命令集

| 命令 | 说明 |
|---|---|
| `plan "<目标>" [--scenario S] [--verbose]` | 输入一句话，生成完整安排（S1–S5 主线）。 |
| `replan "<反馈>"` | 对最近一次方案做局部调整（锁其余 · 换一处）。 |
| `reflect [--id ID] [--verbose]` | 查看某次会话的反思信息，默认最近一次。 |
| `history [--id ID] [--verbose]` | 列出历史记录，或查看某次详情。 |
| `profile show` / `profile edit [--user-pref-delta ...] [--scenario-override key=value]` | 查看或编辑已学习的偏好。 |
| `demo family\|friend\|date\|solo` | 运行预设场景，端到端走一遍主线。 |

## 四场景

家庭 / 朋友 / 约会 / 单人，共用同一套 ConstraintEngine，各自挂一份 ScenarioTemplate（硬约束基线 + 软权重覆盖 + 风险增项）。路由按同行人优先级：**家庭 > 约会 > 朋友 > 单人**；句中无同行人时归为单人。

## 能力模型（4 + 1）

- **意图理解**：一句自然语言 → 结构化 IntentFrame（六维偏好 + 敏感项 + 同行人），命中规则带文本 span，可回放。
- **场景化**：按同行人路由四模板，权重与硬约束随场景切换。
- **数据飞轮**：会话末产出用户偏好增量 / 场景覆盖 / 商家信号，下次开局注入评分。
- **思考深度**：约束分层（硬过滤 / 软评分 / 风险扣分），每条约束携带来源标签（本次目标 / 家庭档案 / 历史学习）。
- **本地实时执行（+1）**：动线收敛（按 geo 累加通勤、跨区扣分）、实时兜底（资源校验触发局部重规划）、服务整合（POI / 团购 / 预约 / 配送 / 支付一链路打通）。

## 五幕主线 S1–S5

- **S1 意图理解**：解析目标，给出安排依据与场景判定。
- **S2 方案呈现**：产出 A/B 双方案，标注路线、总耗时、锁定 / 可调项。
- **S3 确认与执行**：拆分可逆动作与资金确认，逐工具推进；实时兜底在此触发。
- **S4 反馈与微调**：同行人反馈或系统兜底走同一局部重规划原语，对费用差额再确认。
- **S5 行程交付 + 飞轮固化**：输出分人行程与转发文案，会话信号写回飞轮。

## 双模式输出

默认（user 视角，不加 `--verbose`）只输出四模块：

- **安排依据**：取自方案约束的 reason。
- **安心保障**：可逆性、资金安全等描述。
- **退改说明**：可退改触点与资金项拆分。
- **已确定 / 可调整**：哪些锁定、哪些可调。

`--verbose` 在四模块之外展开：意图解析细节、候选数量、评分与风险扣分、tool I/O、信号注入与产出。

## 数据飞轮

连跑两次会话，第二次开局可见"基于历史调整"与方案差异（如某商户被降权后从首选剔除、低耗时动线被提权）。信号写入 `data/learned/`，运行记录写入 `data/runs/`。核对脚本与预期差异见 `data/test_scenarios/two_session_flywheel.md`。

## 工具与 MockClient

10 个 mock tool 收在 `mock/tools.py` 的 `MockClient` 适配边界后，入参 / 出参形如真实接口：

| 工具 | 对应真实服务 |
|---|---|
| `mock_poi_query` | POI / 商户搜索 |
| `mock_groupbuy` | 团购详情 |
| `mock_check_inventory` | 库存 / SKU |
| `mock_queue` | 排队取号 |
| `mock_delivery` | 即时 / 定时配送 |
| `mock_mobility` | 出行路线 |
| `mock_reserve` | 餐饮预约 |
| `mock_pay` | 支付收银 |
| `mock_geo_minutes` | ETA / 通勤时长 |
| `mock_weather` | 天气风险 |

接真实 API 时只替换 `MockClient` 实现、不动调用方。失败注入（售罄 / 满位 / 券失效）触发 `resource_checker` 兜底。

## 执行触点

- **render_share**：生成可转发的方案文案。
- **惊喜配送**：蛋糕 / 鲜花定时送达餐厅。
- **排队取号兜底**：满位时取号并利用等位窗口完成附近活动。

## 异常处理

`resource_checker` 监测营业 / 余位 / 拥挤 / 券有效期 / 天气，产出 `fallback_event`；`replanner` 以「锁其余 · 换一处」局部重规划，并对费用差额再确认。同行人反馈与系统兜底共用同一局部重规划原语。

## 项目结构

```
meituan-arrange-cli/
├── cli/                  # 命令行层
│   ├── main.py           #   入口与命令路由（plan/replan/reflect/history/profile/demo）
│   ├── render.py         #   user / verbose 双模式渲染
│   └── session.py        #   会话、档案、运行记录读写
├── core/                 # 决策内核
│   ├── intent_ontology.py / intent_parser.py   # 关键词规则表 + 意图解析
│   ├── scenario_router.py / scenario_templates/ # 场景路由 + 四模板
│   ├── constraint_engine.py                    # 硬过滤 / 软评分(含动线) / 风险 / 排序
│   ├── planner.py / replanner.py / flywheel.py  # 规划 / 局部重规划 / 飞轮
│   ├── executor.py / resource_checker.py        # 执行编排 / 实时资源校验兜底
│   └── itinerary_generator.py                   # 分人行程生成
├── models/               # 数据契约 + presenter（输出模式边界）
├── mock/                 # repository.py 本地数据 · tools.py(MockClient+10 工具) · data/*.json
├── scenarios/            # 四场景对外封装
├── data/                 # learned/(信号) · runs/(运行记录) · test_scenarios/(核对说明)
├── scripts/              # 端到端与两次会话脚本
├── tests/                # 回归测试
├── demo.py / e2e.py      # 引擎侧演示脚本
└── EXPORTS.md            # 对外接口契约（供集成方导入）
```

## 端到端验证

```bash
python -m unittest discover -s tests       # 回归测试（28 项）
python e2e.py                              # 四场景主线 + 自身状态 replan + 两次会话 + 模式对照
python cli/main.py demo solo               # CLI 走完一个场景主线（family/friend/date/solo）
```

两次会话飞轮的输入与预期差异另见 `data/test_scenarios/two_session_flywheel.md`。

## 真实数据接入

`mock/` 层即真实数据面的替身：`MockClient` 的出入参与真实接口同形。替换 `MockClient` 实现即可接入真实 POI / 团购 / 库存 / 排队 / 配送 / 出行 / 支付 / ETA / 天气接口，调用方无需改动。

## 设计文档

接口契约见 `EXPORTS.md`，阶段说明见 `scripts/README_STEP4.md`。
产品说明文档：https://icnaohlo7li1.feishu.cn/wiki/GLlLwtODEic8rEksOG7cwyuUnCe?from=from_copylink
=======
>>>>>>> 35b5aa6435ee2aa0839c29dc3e67a42a1312d3c1
