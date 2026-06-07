"""验收标准的回归测试（标准库 unittest）。

运行： python -m unittest -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    Profile, LearnedSignals, SessionState, SOURCE_LEARNED,
    render_user, render_verbose, assert_user_safe, USER_KEYS, VERBOSE_EXTRA_KEYS,
)
from core import intent_parser, scenario_router, planner
from core.constraint_engine import rank
from core.flywheel import Flywheel
from core import replanner
from mock.repository import get_repository


def pipeline(goal, profile, signals=None):
    intent = intent_parser.parse(goal, profile)
    scenario = scenario_router.route(intent, profile)
    constraint = planner.build_constraints(intent, scenario, signals, profile)
    plans = planner.generate_plans(intent, scenario, constraint, signals, profile)
    return intent, scenario, constraint, rank(plans, use_route_weight=True)


class TestAcceptance(unittest.TestCase):
    def setUp(self):
        self.profile = Profile(home_geo="central", has_kids=True,
                               standing_prefs={"spend": "省"})

    def test_distinct_inputs_distinct_outputs(self):
        i1, s1, _, p1 = pipeline("带孩子去晒太阳吃顿好的", self.profile)
        i2, s2, _, p2 = pipeline("和朋友一帮人出来嗨玩起来", self.profile)
        self.assertNotEqual(s1.id, s2.id)
        self.assertNotEqual(i1.vibe, i2.vibe) if (i1.vibe or i2.vibe) else None
        self.assertNotEqual(p1[0].id, p2[0].id)
        # fired_rules 带 name 与 span
        self.assertTrue(i1.fired_rules)
        for name, span in i1.fired_rules:
            self.assertIsInstance(name, str)
            self.assertEqual(len(span), 2)
            self.assertLessEqual(span[0], span[1])

    def test_solo_routing(self):
        intent, scenario, constraint, _ = pipeline("我自己一个人随便逛逛减脂", self.profile)
        self.assertEqual(intent.party, ["user"])
        self.assertEqual(scenario.id, "solo")
        # 硬约束/权重与 family 明显不同
        _, fam_sc, fam_c, _ = pipeline("带孩子出去玩", self.profile)
        solo_hard = {c.hard.field for c in constraint.hard}
        fam_hard = {c.hard.field for c in fam_c.hard}
        self.assertIn("solo_friendly", solo_hard)
        self.assertNotIn("solo_friendly", fam_hard)
        self.assertNotEqual(scenario.weight_overrides, fam_sc.weight_overrides)

    def test_route_weight_changes_rank(self):
        intent, scenario, constraint, _ = pipeline("带孩子去晒太阳吃顿好的", self.profile)
        plans = planner.generate_plans(intent, scenario, constraint, None, self.profile)
        on = [p.id for p in rank(list(plans), use_route_weight=True)]
        off = [p.id for p in rank(list(plans), use_route_weight=False)]
        self.assertNotEqual(on, off)
        # 所有 plan 携带 route_minutes
        self.assertTrue(all(p.route_minutes >= 0 for p in plans))

    def test_two_session_learning_injection(self):
        path = os.path.join(os.path.dirname(__file__), "_tmp_signals.json")
        if os.path.exists(path):
            os.remove(path)
        fw = Flywheel(path=path)

        sig1 = fw.load()
        self.assertTrue(sig1.is_empty())
        i1, s1, _, ranked1 = pipeline("我一个人拍照出片喝咖啡", self.profile, sig1)
        fw.emit(sig1, i1, s1.id, ranked1[0], feedback="like")

        sig2 = fw.load()
        self.assertFalse(sig2.is_empty())
        _, _, c2, _ = pipeline("我一个人拍照出片喝咖啡", self.profile, sig2)
        learned = [s for s in c2.soft if s.source == SOURCE_LEARNED]
        self.assertTrue(learned)

        os.remove(path)

    def test_flywheel_evolves_and_persists(self):
        path = os.path.join(os.path.dirname(__file__), "_tmp_evo.json")
        if os.path.exists(path):
            os.remove(path)
        fw = Flywheel(path=path)

        # 会话1：空白起步 → emit 至少 3 条历史学习项并落盘
        s1 = fw.load()
        self.assertTrue(s1.is_empty())
        i1, sc1, _, r1 = pipeline("我一个人拍照出片喝咖啡", self.profile, s1)
        s1, rec1 = fw.emit(s1, i1, sc1.id, r1[0], feedback="like")
        self.assertGreaterEqual(len(rec1.signals_emitted), 3)
        self.assertTrue(os.path.exists(path))

        # 会话2：加载持久化信号 → 再次 emit 应在原值上演化（增量变大）
        s2 = fw.load()
        self.assertFalse(s2.is_empty())
        before = dict(s2.user_pref_deltas)
        i2, sc2, _, r2 = pipeline("我一个人拍照出片喝咖啡", self.profile, s2)
        s2, _ = fw.emit(s2, i2, sc2.id, r2[0], feedback="like")
        self.assertGreater(s2.user_pref_deltas["vibe"], before["vibe"])

        os.remove(path)

    def test_four_scenarios_ab_differentiated(self):
        cases = {
            "family": "带孩子周末出去玩晒太阳吃顿好的",
            "friend": "和闺蜜一帮人聚一下玩起来吃正餐",
            "date": "情侣约会拍照出片找地方坐坐",
            "solo": "一个人放松随便逛逛喝咖啡",
        }
        for sc, goal in cases.items():
            intent, scenario, _, ranked = pipeline(goal, self.profile)
            self.assertEqual(scenario.id, sc)
            ab = planner.select_ab(ranked)
            self.assertEqual(len(ab), 2, f"{sc} 未产出 A/B 双方案")
            a, b = ab
            route_diff = abs(a.route_minutes - b.route_minutes)
            zones_differ = set(a.geo_path()) != set(b.geo_path())
            self.assertTrue(route_diff >= 15 or zones_differ,
                            f"{sc} A/B 区分不足: routeΔ={route_diff} zonesDiffer={zones_differ}")
            self.assertTrue(all(p.route_minutes >= 0 for p in ab))

    def test_scenario_overrides_cross_session(self):
        path = os.path.join(os.path.dirname(__file__), "_tmp_over.json")
        runs = os.path.join(os.path.dirname(__file__), "_tmp_over_runs.jsonl")
        for p in (path, runs):
            if os.path.exists(p):
                os.remove(p)
        fw = Flywheel(path=path, runs_path=runs)
        goal = "一个人就近躺平喝咖啡"

        def eff_weight(c):
            return sum(s.weight for s in c.soft if s.field == "effort")

        # 会话1：表达 effort，结束后沉淀 scenario_overrides[solo]
        s1 = fw.load()
        i1, sc1, c1, r1 = pipeline(goal, self.profile, s1)
        base = eff_weight(c1)
        s1, _ = fw.emit(s1, i1, sc1.id, r1[0])
        self.assertIn("effort", s1.scenario_overrides.get("solo", {}))

        # 会话2：scenario_overrides 介入 → effort 权重提升，全局 user_pref 让位
        s2 = fw.load()
        _, _, c2, _ = pipeline(goal, self.profile, s2)
        self.assertGreater(eff_weight(c2), base)
        self.assertTrue(any(s.field == "effort" and "覆盖" in s.reason for s in c2.soft))
        self.assertFalse(any(s.field == "effort" and "全局" in s.reason for s in c2.soft))

        # 跨场景不串：solo 的 effort 覆盖不作用于 family
        fi, fsc, fc, _ = pipeline("带孩子就近躺平吃顿好的", self.profile, s2)
        self.assertEqual(fsc.id, "family")
        self.assertLess(eff_weight(fc), eff_weight(c2))

        # runs 留痕可读
        self.assertTrue(fw.load_runs())
        for p in (path, runs):
            if os.path.exists(p):
                os.remove(p)

    def test_self_state_replan_solo(self):
        intent, scenario, constraint, ranked = pipeline("一个人放松随便逛逛喝咖啡", self.profile)
        self.assertEqual(scenario.id, "solo")
        session = SessionState(current_intent=intent, current_plan=ranked[0],
                               scenario_id="solo", current_exec_state="planned")

        # 预置模拟输入存在
        preset = get_repository().self_state_input("solo_tired_cancel")
        self.assertIsNotNone(preset)

        # 缩短：无需外部反馈直接触发
        new_plan, diff = replanner.replan_on_self_state(session, preset["text"], self.profile)
        self.assertIsNotNone(diff)
        self.assertEqual(diff.action, "shorten")
        self.assertLess(len(new_plan.slots), len(ranked[0].slots))
        self.assertEqual(session.current_exec_state, "replanned")
        self.assertIs(session.current_plan, new_plan)

        # 延长用餐：动线不变、用餐时长增加
        s2 = SessionState(current_plan=ranked[0], scenario_id="solo")
        meal_before = next(s.duration_min for s in ranked[0].slots if s.kind == "meal")
        p2, d2 = replanner.replan_on_self_state(s2, "想多坐会慢慢吃", self.profile)
        self.assertEqual(d2.action, "extend_meal")
        meal_after = next(s.duration_min for s in p2.slots if s.kind == "meal")
        self.assertGreater(meal_after, meal_before)
        self.assertEqual(p2.route_minutes, ranked[0].route_minutes)

    def test_two_session_observable_plan_diff(self):
        path = os.path.join(os.path.dirname(__file__), "_tmp_2s.json")
        runs = os.path.join(os.path.dirname(__file__), "_tmp_2s.jsonl")
        for p in (path, runs):
            if os.path.exists(p):
                os.remove(p)
        fw = Flywheel(path=path, runs_path=runs)
        prof = Profile(home_geo="central")
        goal = "一个人放松随便逛逛喝咖啡"

        s1 = fw.load()
        self.assertTrue(s1.is_empty())
        i1, sc1, _, r1 = pipeline(goal, prof, s1)
        a1 = planner.select_ab(r1)[0]
        self.assertIn("res_noodle", [s.ref_id for s in a1.slots])
        s1, _ = fw.emit(s1, i1, sc1.id, a1, feedback="dislike")
        self.assertEqual(s1.merchant_signals["res_noodle"], -0.5)

        s2 = fw.load()
        self.assertFalse(s2.is_empty())
        i2, sc2, _, r2 = pipeline(goal, prof, s2)
        a2 = planner.select_ab(r2)[0]
        self.assertNotIn("res_noodle", [s.ref_id for s in a2.slots])
        self.assertIn("res_dimsum", [s.ref_id for s in a2.slots])
        for p in (path, runs):
            if os.path.exists(p):
                os.remove(p)

    def test_output_mode_boundary(self):
        intent, scenario, constraint, ranked = pipeline("情侣约会拍照出片找地方坐坐", self.profile)
        plan = ranked[0]

        user = render_user(plan, constraint)
        self.assertEqual(set(user.keys()), set(USER_KEYS))
        assert_user_safe(user)  # 不抛异常

        verbose = render_verbose(plan, constraint,
                                 candidate_pool=["a", "b"],
                                 rejected_merchants=[{"merchant_id": "x", "reason": "售罄"}],
                                 signals=LearnedSignals(user_pref_deltas={"vibe": 0.2}),
                                 tool_io=[{"tool": "geo", "out": 12}])
        # verbose 含 user 四项 + 额外项
        for k in USER_KEYS:
            self.assertIn(k, verbose)
        for k in VERBOSE_EXTRA_KEYS:
            self.assertIn(k, verbose)
        # user 模式严禁泄露任何 verbose 字段
        for k in VERBOSE_EXTRA_KEYS:
            self.assertNotIn(k, user)
        with self.assertRaises(AssertionError):
            assert_user_safe(verbose)

    def test_fallback_participates_in_signals(self):
        intent, scenario, constraint, ranked = pipeline("我一个人拍照出片喝咖啡", self.profile)
        new_plan, diff = replanner.replan(ranked[0], slot_index=0, constraint=constraint,
                                          profile=self.profile, fallback_triggered=True)
        self.assertIsNotNone(diff)
        self.assertTrue(diff.fallback_triggered)
        self.assertTrue(new_plan.rejected_merchants)

        fw = Flywheel(path=os.path.join(os.path.dirname(__file__), "_tmp_fb.json"))
        sig, rec = fw.emit(LearnedSignals(), intent, scenario.id, new_plan,
                           feedback="like", replanned=True,
                           fallback_triggered=True, persist=False)
        self.assertTrue(rec.fallback_triggered)
        self.assertTrue(any("fallback" in s for s in rec.signals_emitted))


if __name__ == "__main__":
    unittest.main()
