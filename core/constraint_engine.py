"""约束引擎：filter_hard / score_soft / apply_risk / rank。

score_soft 为单候选软评分；动线权重在 plan 层（rank）按 route_minutes 折算扣分，
可通过 use_route_weight 开关，用于"开/关动线"对照。
"""

from __future__ import annotations

from typing import Callable, Dict, List

# 约束类的定义真源在 models/，此处再导出，使 `from core.constraint_engine import ...` 可用
from models import Constraint, ConstraintItem, RiskItem, HardConstraint, RiskRule, SoftPref, Plan

# 有序量纲，用于 effort / spend 的渐进匹配
_EFFORT_SCALE = {"躺平": 0, "轻度": 1, "能折腾": 2}
_SPEND_SCALE = {"省": 0, "适中": 1, "不在乎": 2}

ROUTE_PENALTY_PER_MIN = 0.10    # 每分钟通勤折算的扣分


def _graded(scale: Dict[str, int], a, b) -> float:
    if a is None or b is None or a not in scale or b not in scale:
        return 0.0
    dist = abs(scale[a] - scale[b])
    if dist == 0:
        return 1.0
    if dist == 1:
        return 0.5
    return 0.0


def _eq_match(cand, attr, target) -> float:
    if target is None:
        return 0.0
    return 1.0 if getattr(cand, attr, None) == target else 0.0


def _bool_match(cand, attr) -> float:
    return 1.0 if getattr(cand, attr, False) else 0.0


# field -> (candidate, target) -> [0,1]
_MATCHERS: Dict[str, Callable] = {
    "vibe": lambda c, t: _eq_match(c, "vibe", t),
    "setting": lambda c, t: _eq_match(c, "setting", t),
    "meal_focus": lambda c, t: _eq_match(c, "meal_focus", t),
    "effort": lambda c, t: _graded(_EFFORT_SCALE, getattr(c, "effort", None), t),
    "spend": lambda c, t: _graded(_SPEND_SCALE, getattr(c, "spend", None), t),
    "photogenic": lambda c, t: _bool_match(c, "photogenic"),
    "kid_balance": lambda c, t: _bool_match(c, "kid_friendly"),
    "low_intensity": lambda c, t: _bool_match(c, "low_intensity"),
    "solo_pref": lambda c, t: _bool_match(c, "solo_friendly"),
    "low_cal": lambda c, t: _bool_match(c, "low_cal"),
    "group_lively": lambda c, t: 1.0 if getattr(c, "vibe", None) in ("热闹", "出片") else 0.0,
}


def _hard_ok(cand, rule: HardConstraint) -> bool:
    actual = getattr(cand, rule.field, None)
    op = rule.op
    if op == "true":
        return bool(actual) is True
    if op == "false":
        return bool(actual) is False
    if op == "eq":
        return actual == rule.value
    if op == "ne":
        return actual != rule.value
    if op == "in":
        return actual in (rule.value or [])
    if op == "contains":
        return rule.value in (actual or [])
    return True


def filter_hard(candidates: list, hard_rules: List[HardConstraint]) -> list:
    return [c for c in candidates if all(_hard_ok(c, r) for r in hard_rules)]


def score_soft(candidate, soft_prefs: List[SoftPref]) -> float:
    total = 0.0
    for pref in soft_prefs:
        matcher = _MATCHERS.get(pref.field)
        if matcher is None:
            continue
        total += pref.weight * matcher(candidate, pref.target)
    return total


def _risk_hit(cand, rule: RiskRule) -> bool:
    actual = getattr(cand, rule.field, None)
    op = rule.op
    if op == "true":
        return bool(actual) is True
    if op == "false":
        return bool(actual) is False
    if op == "eq":
        return actual == rule.value
    if op == "ne":
        return actual != rule.value
    if op == "gt":
        try:
            return actual > rule.value
        except TypeError:
            return False
    return False


def apply_risk(candidates: list, risk_rules: List[RiskRule]) -> float:
    penalty = 0.0
    for cand in candidates:
        for rule in risk_rules:
            if _risk_hit(cand, rule):
                penalty += rule.penalty
    return penalty


def route_penalty(route_minutes: int) -> float:
    return route_minutes * ROUTE_PENALTY_PER_MIN


def rank(plans: List[Plan], use_route_weight: bool = True) -> List[Plan]:
    """按 total_score 降序排列。use_route_weight=False 时忽略动线扣分。"""
    for p in plans:
        total = p.soft_score - p.risk_penalty
        if use_route_weight:
            total -= route_penalty(p.route_minutes)
        p.total_score = total
        p.score = total  # 对外契约字段镜像
    return sorted(plans, key=lambda p: p.total_score, reverse=True)
