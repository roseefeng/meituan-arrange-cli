"""验收标准的回归测试（标准库 unittest）。

运行： python -m unittest -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Profile, LearnedSignals, SOURCE_LEARNED
from core import intent_parser, scenario_router, planner
from core.constraint_engine import rank
from core.flywheel import Flywheel
from core import replanner


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
