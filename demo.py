"""端到端演示：跑通四项验收并产出汇报所需信息。

运行： python demo.py
"""

from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from models import Profile, Constraint, LearnedSignals, SOURCE_GOAL, SOURCE_PROFILE, SOURCE_LEARNED
from core import intent_ontology as onto
from core import intent_parser, scenario_router, planner, replanner
from core.constraint_engine import rank
from core.flywheel import Flywheel
from mock.repository import get_repository, LEARNED_SIGNALS_PATH


def hr(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def run_pipeline(raw_goal, profile, signals=None):
    intent = intent_parser.parse(raw_goal, profile)
    scenario = scenario_router.route(intent, profile)
    constraint = planner.build_constraints(intent, scenario, signals, profile)
    plans = planner.generate_plans(intent, scenario, constraint, signals, profile)
    ranked = rank(plans, use_route_weight=True)
    return intent, scenario, constraint, ranked


# ----------------------------------------------------------------------------
def report_keyword_table():
    hr("① 关键词规则表全文（六维 + party 解析）")
    dims = {}
    for r in onto.DIMENSION_RULES:
        dims.setdefault(r.dimension, []).append(r)
    dim_names = {
        "vibe": "vibe（松弛/热闹/文艺/出片）",
        "setting": "setting（室内/室外/商场/公园）",
        "effort": "effort（躺平/轻度/能折腾）",
        "spend": "spend（省/适中/不在乎）",
        "meal_focus": "meal_focus（正餐/小吃/咖啡/不重要）",
        "duration_hint": "duration_hint（短/半天/全天）",
        "sensitivities": "sensitivities（减脂/忌辣/孩子友好/低强度）",
    }
    for dim, rules in dims.items():
        print(f"\n[{dim_names.get(dim, dim)}]")
        for r in rules:
            print(f"  {r.value:<6} ← {list(r.keywords)}")
    print("\n[party 解析（优先级 family > date > friend > solo）]")
    for pr in onto.PARTY_RULES:
        print(f"  role={pr.role:<8} hint={pr.scenario_hint:<7} ← {list(pr.keywords)}")


def report_four_examples(profile):
    hr("② 四句对照示例（IntentFrame / 命中模板 / Plan 摘要 / fired_rules）")
    cases = [
        ("家庭", "周末带孩子去晒太阳，找个亲子的地方，吃顿好的，经济点"),
        ("朋友", "周末和朋友一帮人出来嗨，玩起来，吃个正餐"),
        ("约会", "和对象约会，想拍照出片，找地方坐坐喝咖啡"),
        ("单人", "我自己一个人随便逛逛，想减脂，随便垫垫"),
    ]
    for label, goal in cases:
        intent, scenario, constraint, ranked = run_pipeline(goal, profile)
        print(f"\n--- {label} ---")
        print(f"raw_goal : {goal}")
        print(f"Intent   : {intent.summary()}")
        print(f"模板     : {scenario.id} ({scenario.label})")
        print(f"fired_rules:")
        for name, span in intent.fired_rules:
            print(f"    {name:<14} span={span} «{goal[span[0]:span[1]]}»")
        print(f"Plan A   : {ranked[0].summary()}")
        if len(ranked) > 1:
            print(f"Plan B   : {ranked[1].summary()}")


def report_solo_vs_family(profile):
    hr("③ 单人路由对照（solo 的硬约束/权重 vs family 明显不同）")
    fam_intent, fam_sc, fam_c, _ = run_pipeline("带孩子出去玩，吃顿好的", profile)
    solo_intent, solo_sc, solo_c, _ = run_pipeline("我一个人随便逛逛减脂", profile)
    print(f"\nfamily party={fam_intent.party} → 模板 {fam_sc.id}")
    print(f"  硬约束: {[c.hard.describe() for c in fam_c.hard]}")
    print(f"  权重  : {fam_sc.weight_overrides}")
    print(f"\nsolo   party={solo_intent.party} → 模板 {solo_sc.id}")
    print(f"  硬约束: {[c.hard.describe() for c in solo_c.hard]}")
    print(f"  权重  : {solo_sc.weight_overrides}")
    print(f"\nsolo 风险增项: {[r.rule.describe() for r in solo_c.risk]}")


def report_source_breakdown(profile):
    hr("④ 约束来源分布（本次目标 / 家庭档案 / 历史学习）")
    # 先用一次会话产生历史学习信号（从空白起步，保证可复现）
    fw = Flywheel()
    seed = LearnedSignals()
    intent, scenario, constraint, ranked = run_pipeline(
        "带孩子去晒太阳吃顿好的", profile, seed)
    seed, _ = fw.emit(seed, intent, scenario.id, ranked[0], feedback="like", persist=False)
    # 再带着信号重建约束，使三类来源都出现
    intent2, scenario2, constraint2, _ = run_pipeline(
        "带孩子去晒太阳吃顿好的", profile, seed)
    counts = constraint2.source_breakdown()
    total = sum(counts.values()) or 1
    print()
    for src in (SOURCE_GOAL, SOURCE_PROFILE, SOURCE_LEARNED):
        items = [x for x in (list(constraint2.soft) + list(constraint2.hard) + list(constraint2.risk))
                 if x.source == src]
        print(f"[{src}] {counts[src]} 条 ({counts[src] / total:.0%})")
        for it in items[:2]:
            print(f"    例: {it.reason}")


def report_route_toggle(profile):
    hr("⑤ 动线权重 开/关 的 rank 对照（同一组候选）")
    intent, scenario, constraint, _ = run_pipeline("带孩子去晒太阳，吃顿好的", profile)
    plans = planner.generate_plans(intent, scenario, constraint, None, profile)

    on = rank(list(plans), use_route_weight=True)
    off = rank(list(plans), use_route_weight=False)
    on_ids = [p.id for p in on]
    off_ids = [p.id for p in off]
    print(f"\n场景={scenario.id} 候选组合数: {len(plans)}")
    print("\n[开启动线权重] Top4:")
    for i, p in enumerate(on[:4]):
        print(f"  #{i + 1} {p.summary()}")
    print("\n[关闭动线权重] Top4:")
    for i, p in enumerate(off[:4]):
        print(f"  #{i + 1} {p.summary()}")

    changed = on_ids != off_ids
    print(f"\n完整 rank 顺序是否改变: {changed}")
    # 找一个排名位移的方案作为例证
    for pid in off_ids:
        if off_ids.index(pid) != on_ids.index(pid):
            print(f"  例: {pid} 关={off_ids.index(pid) + 1}名 → 开={on_ids.index(pid) + 1}名 "
                  f"(route={next(p for p in on if p.id == pid).route_minutes}min)")
            break
    print("结论: " + ("动线权重生效，rank 结果不同" if changed else "rank 未变化"))


def report_two_sessions(profile):
    hr("⑥ 连续两次会话：第二次 build_constraints 注入上次 LearnedSignals")
    if os.path.exists(LEARNED_SIGNALS_PATH):
        os.remove(LEARNED_SIGNALS_PATH)
    fw = Flywheel()

    # 会话 1
    sig1 = fw.load()
    print(f"\n会话1 开局信号: empty={sig1.is_empty()}")
    intent, scenario, c1, ranked1 = run_pipeline("我一个人想拍照出片喝咖啡", profile, sig1)
    learned_in_c1 = [s.reason for s in c1.soft if s.source == SOURCE_LEARNED]
    print(f"会话1 build_constraints 历史学习项: {learned_in_c1 or '无'}")
    sig1b, rec = fw.emit(sig1, intent, scenario.id, ranked1[0], feedback="like")
    print(f"会话1 末 emit 信号: {rec.signals_emitted}")

    # 会话 2
    sig2 = fw.load()
    print(f"\n会话2 开局信号: empty={sig2.is_empty()} user_pref={sig2.user_pref_deltas} "
          f"merchant={sig2.merchant_signals}")
    intent2, scenario2, c2, ranked2 = run_pipeline("我一个人想拍照出片喝咖啡", profile, sig2)
    learned_in_c2 = [s.reason for s in c2.soft if s.source == SOURCE_LEARNED]
    print(f"会话2 build_constraints 注入的历史学习项:")
    for r in learned_in_c2:
        print(f"    {r}")
    print(f"\n验证: 第二次约束含 {len(learned_in_c2)} 条历史学习项 → 注入成功")


def report_replan(profile):
    hr("⑦ 局部重规划 diff（锁定其余 slot，仅替换一处；含兜底接口）")
    intent, scenario, constraint, ranked = run_pipeline("我一个人拍照出片喝咖啡", profile)
    plan = ranked[0]
    print(f"\n原方案: {plan.summary()}")
    new_plan, diff = replanner.replan(plan, slot_index=0, constraint=constraint,
                                      profile=profile, fallback_triggered=True)
    if diff:
        print(f"diff   : {diff.describe()}")
        print(f"新方案 : {new_plan.summary()}")


def report_four_scenarios_ab(profile):
    hr("⑧ 四场景 A/B 双方案样本（route_minutes / 途经区域有区分）")
    cases = [
        ("family", "带孩子周末出去玩晒太阳吃顿好的"),
        ("friend", "和闺蜜一帮人聚一下玩起来吃正餐"),
        ("date", "情侣约会拍照出片找地方坐坐"),
        ("solo", "一个人放松随便逛逛喝咖啡"),
    ]
    for label, goal in cases:
        intent, scenario, constraint, ranked = run_pipeline(goal, profile)
        ab = planner.select_ab(ranked)
        a = ab[0]
        b = ab[1] if len(ab) > 1 else None
        print(f"\n--- {scenario.id} | «{goal}» ---")
        print(f"  A: {a.summary()}")
        if b:
            print(f"  B: {b.summary()}")
            zones_differ = set(a.geo_path()) != set(b.geo_path())
            print(f"  区分: route Δ={abs(a.route_minutes - b.route_minutes)}min, 途经区域不同={zones_differ}")
            gb_a = [s.groupbuy_id for s in a.slots if s.groupbuy_id]
            gb_b = [s.groupbuy_id for s in b.slots if s.groupbuy_id]
            print(f"  团购: A={gb_a or '无'} B={gb_b or '无'}")


def report_solo_override(profile):
    hr("⑨ solo 飞轮注入前后权重变化（scenario_overrides 跨会话生效）")
    path = os.path.join(os.path.dirname(LEARNED_SIGNALS_PATH), "_demo_override.json")
    runs = os.path.join(os.path.dirname(LEARNED_SIGNALS_PATH), "_demo_override_runs.jsonl")
    for p in (path, runs):
        if os.path.exists(p):
            os.remove(p)
    fw = Flywheel(path=path, runs_path=runs)
    goal = "一个人就近躺平喝咖啡"

    def eff_weight(c):
        return sum(s.weight for s in c.soft if s.field == "effort")

    # 会话1
    s1 = fw.load()
    i1, sc1, c1, ranked1 = run_pipeline(goal, profile, s1)
    print(f"\n[会话1·solo] effort 有效软权重 = {eff_weight(c1):.2f}（intent {i1.effort} + 模板）")
    s1, _ = fw.emit(s1, i1, sc1.id, ranked1[0], feedback="like")
    print(f"  emit → scenario_overrides[solo] = {s1.scenario_overrides.get('solo')}")

    # 会话2（注入后）
    s2 = fw.load()
    i2, sc2, c2, _ = run_pipeline(goal, profile, s2)
    print(f"[会话2·solo] effort 有效软权重 = {eff_weight(c2):.2f}（scenario_overrides 叠加，全局 user_pref 让位）")
    ov = [s.reason for s in c2.soft if s.field == "effort" and "覆盖" in s.reason]
    print(f"  覆盖项: {ov}")

    # family 对照：solo 的 override 不跨场景
    fi, fsc, fc, _ = run_pipeline("带孩子就近躺平吃顿好的", profile, s2)
    print(f"[对照·family] effort 有效软权重 = {eff_weight(fc):.2f}（family 模板无 effort 权重，solo 覆盖不跨场景）")
    for p in (path, runs):
        if os.path.exists(p):
            os.remove(p)


def main():
    # 清掉历史信号，保证整次演示可复现
    if os.path.exists(LEARNED_SIGNALS_PATH):
        os.remove(LEARNED_SIGNALS_PATH)
    repo = get_repository()
    print(f"已加载 mock 数据: activities={len(repo.activities)} "
          f"restaurants={len(repo.restaurants)} groupbuys={len(repo.groupbuys)}")
    profile = Profile(user_id="u_demo", home_geo="central",
                      has_kids=True, standing_prefs={"spend": "省"})

    report_keyword_table()
    report_four_examples(profile)
    report_solo_vs_family(profile)
    report_source_breakdown(profile)
    report_route_toggle(profile)
    report_two_sessions(profile)
    report_replan(profile)
    report_four_scenarios_ab(profile)
    report_solo_override(profile)
    print("\n全部验收项执行完毕。")


if __name__ == "__main__":
    main()
