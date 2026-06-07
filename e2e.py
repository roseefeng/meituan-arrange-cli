"""四场景端到端脚本（本地 mock，全程无网络）。

覆盖：family/friend/date/solo 主线 → A/B 双方案 → solo 自身状态 replan
     → 两次会话飞轮差异 → user / verbose 输出模式对照。

运行： python e2e.py
"""

from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from models import (
    Profile, SessionState, LearnedSignals,
    render_user, render_verbose, assert_user_safe, format_user, format_verbose,
)
from core import intent_parser, scenario_router, planner, replanner
from core.constraint_engine import rank
from core.flywheel import Flywheel
from mock.repository import get_repository, LEARNED_SIGNALS_PATH, RUNS_PATH


def hr(t):
    print("\n" + "=" * 76 + f"\n{t}\n" + "=" * 76)


def plan_session(goal, profile, signals=None, repo=None):
    intent = intent_parser.parse(goal, profile)
    scenario = scenario_router.route(intent, profile)
    constraint = planner.build_constraints(intent, scenario, signals, profile)
    ranked = rank(planner.generate_plans(intent, scenario, constraint, signals, profile, repo), True)
    ab = planner.select_ab(ranked)
    return intent, scenario, constraint, ranked, ab


def run_four_scenarios(profile, repo):
    hr("① 四场景主线 → A/B 双方案")
    cases = [
        ("family", "带孩子周末出去玩晒太阳吃顿好的"),
        ("friend", "和闺蜜一帮人聚一下玩起来吃正餐"),
        ("date", "情侣约会拍照出片找地方坐坐"),
        ("solo", "一个人放松随便逛逛喝咖啡"),
    ]
    last = None
    for sid, goal in cases:
        intent, scenario, constraint, ranked, ab = plan_session(goal, profile, None, repo)
        assert scenario.id == sid, f"路由错误 {scenario.id}!={sid}"
        assert len(ab) == 2, f"{sid} 未产出 A/B"
        a, b = ab
        diff = abs(a.route_minutes - b.route_minutes)
        zones = set(a.geo_path()) != set(b.geo_path())
        assert diff >= 15 or zones, f"{sid} A/B 区分不足"
        print(f"\n[{sid}] «{goal}»")
        print(f"  A: {a.summary()}")
        print(f"  B: {b.summary()}")
        print(f"  区分: routeΔ={diff}min 区域不同={zones}")
        if sid == "solo":
            last = (intent, scenario, constraint, a)
    return last


def run_self_state(solo_ctx, profile, repo):
    hr("② solo 自身状态变更 → 无外部反馈直接 replan")
    intent, scenario, constraint, plan = solo_ctx
    session = SessionState(current_intent=intent, current_plan=plan,
                           scenario_id="solo", current_exec_state="planned")
    preset = repo.self_state_input("solo_tired_cancel")
    print(f"\n原方案: {plan.summary()}")
    print(f"自身状态输入(预置 {preset['id']}): «{preset['text']}»")
    new_plan, diff = replanner.replan_on_self_state(session, preset["text"], profile)
    assert diff is not None and diff.action == "shorten"
    print(f"diff   : {diff.describe()}")
    print(f"新方案 : {new_plan.summary()}")
    print(f"exec_state: {session.current_exec_state}")

    # 延长用餐
    s2 = SessionState(current_plan=plan, scenario_id="solo")
    p2, d2 = replanner.replan_on_self_state(s2, repo.self_state_input("solo_extend_meal")["text"], profile)
    print(f"另一触发: {d2.describe()}")


def run_two_session(profile):
    hr("③ 两次会话飞轮差异（dislike → 商户降权 → 方案变化）")
    tmp, tmpr = "mock/data/_e2e.json", "mock/data/_e2e.jsonl"
    for p in (tmp, tmpr):
        if os.path.exists(p):
            os.remove(p)
    fw = Flywheel(path=tmp, runs_path=tmpr)
    goal = "一个人放松随便逛逛喝咖啡"

    s1 = fw.load()
    print(f"\n会话1 开局信号 empty={s1.is_empty()}")
    i1, sc1, _, _, ab1 = plan_session(goal, profile, s1)
    print(f"会话1 A: {ab1[0].summary()}")
    s1, rec = fw.emit(s1, i1, sc1.id, ab1[0], feedback="dislike")
    print(f"会话1 反馈=dislike → merchant_signals={s1.merchant_signals}")

    s2 = fw.load()
    print(f"\n会话2 开局信号 empty={s2.is_empty()}（已加载上轮）")
    i2, sc2, _, _, ab2 = plan_session(goal, profile, s2)
    print(f"会话2 A: {ab2[0].summary()}")
    s1_ids = [s.ref_id for s in ab1[0].slots]
    s2_ids = [s.ref_id for s in ab2[0].slots]
    print(f"差异: 餐饮 {('res_noodle' in s1_ids)} → 被剔除={('res_noodle' not in s2_ids)}; "
          f"新增 res_dimsum={'res_dimsum' in s2_ids}")
    print(f"history(runs) 可读条数: {len(fw.load_runs())}")
    for p in (tmp, tmpr):
        if os.path.exists(p):
            os.remove(p)


def run_output_modes(profile, repo):
    hr("④ 输出模式边界：user（默认） vs verbose（--verbose）")
    intent, scenario, constraint, ranked, ab = plan_session("情侣约会拍照出片找地方坐坐", profile, None, repo)
    plan = ab[0]

    cand = [f"{a.name}@{a.geo}" for a in repo.activities_for(scenario.id)][:4]
    rejected = [{"merchant_id": "res_hotpot", "reason": "约会场景氛围过吵闹(risk)"}]
    user = render_user(plan, constraint)
    assert_user_safe(user)
    verbose = render_verbose(plan, constraint, candidate_pool=cand,
                             rejected_merchants=rejected,
                             signals=LearnedSignals(user_pref_deltas={"vibe": 0.2}),
                             tool_io=[{"tool": "mock_geo_minutes", "in": "central→uptown", "out": 52}])

    print("\n--- user 模式（仅四项，不泄露调试信息）---")
    print(format_user(user))
    print(f"\nuser 顶层键: {list(user.keys())}")

    print("\n--- verbose 模式（附加候选池/淘汰/原始分/信号/tool I/O）---")
    print(format_verbose(verbose))


def main():
    for p in (LEARNED_SIGNALS_PATH, RUNS_PATH):
        if os.path.exists(p):
            os.remove(p)
    repo = get_repository()
    profile = Profile(user_id="u_demo", home_geo="central", has_kids=True,
                      standing_prefs={"spend": "省"})
    print(f"mock 数据: activities={len(repo.activities)} restaurants={len(repo.restaurants)} "
          f"groupbuys={len(repo.groupbuys)} self_state_inputs={len(repo.self_state_inputs)}")

    solo_ctx = run_four_scenarios(profile, repo)
    run_self_state(solo_ctx, profile, repo)
    run_two_session(profile)
    run_output_modes(profile, repo)
    print("\n端到端四场景执行完毕，无报错。")


if __name__ == "__main__":
    main()
