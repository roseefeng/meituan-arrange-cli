"""Planner：build_constraints（带来源标签）+ generate_plans（含动线评分）。"""

from __future__ import annotations

from typing import List, Optional

from models import (
    IntentFrame, Profile, ScenarioTemplate, LearnedSignals,
    Constraint, ConstraintItem, SoftPref, RiskItem,
    HardConstraint, Plan, PlanSlot,
    SOURCE_GOAL, SOURCE_PROFILE, SOURCE_LEARNED,
)
from core import constraint_engine as engine
from mock.repository import get_repository

_DIMENSION_FIELDS = {"vibe", "setting", "effort", "spend", "meal_focus"}

# 敏感项 → 约束映射
_SENS_HARD = {
    "孩子友好": HardConstraint("kid_friendly", "true", True, label="孩子友好"),
    "低强度": HardConstraint("low_intensity", "true", True, label="低强度（老人/不能久走）"),
    "忌辣": HardConstraint("spicy", "false", True, label="忌辣"),
}
_SENS_SOFT = {
    "减脂": ("low_cal", 2.0, "减脂 → 低卡偏好"),
}


def build_constraints(
    intent: IntentFrame,
    scenario: ScenarioTemplate,
    signals: Optional[LearnedSignals] = None,
    profile: Optional[Profile] = None,
) -> Constraint:
    c = Constraint()
    signals = signals or LearnedSignals()

    # ---------- 本次目标：意图维度软偏好 ----------
    for field in _DIMENSION_FIELDS:
        val = getattr(intent, field, None)
        if val is not None:
            c.soft.append(SoftPref(
                field=field, weight=1.0, source=SOURCE_GOAL,
                reason=f"本次目标: {field}={val}", target=val,
            ))

    # ---------- 本次目标：敏感项 ----------
    for sens in intent.sensitivities:
        if sens in _SENS_HARD:
            hc = _SENS_HARD[sens]
            c.hard.append(ConstraintItem(hard=hc, source=SOURCE_GOAL,
                                         reason=f"本次目标: {hc.label}"))
        elif sens in _SENS_SOFT:
            field, w, why = _SENS_SOFT[sens]
            c.soft.append(SoftPref(field=field, weight=w, source=SOURCE_GOAL,
                                   reason=f"本次目标: {why}", target=None))

    # ---------- 本次目标：场景模板 ----------
    for hc in scenario.base_constraints:
        c.hard.append(ConstraintItem(hard=hc, source=SOURCE_GOAL,
                                     reason=f"本次目标(场景{scenario.label}): {hc.describe()}"))
    for field, weight in scenario.weight_overrides.items():
        target = getattr(intent, field, None) if field in _DIMENSION_FIELDS else None
        c.soft.append(SoftPref(field=field, weight=weight, source=SOURCE_GOAL,
                               reason=f"本次目标(场景{scenario.label}): 权重 {field}={weight}",
                               target=target))
    for rr in scenario.risk_extras:
        c.risk.append(RiskItem(rule=rr, source=SOURCE_GOAL,
                               reason=f"本次目标(场景{scenario.label}): {rr.describe()}"))

    # ---------- 家庭档案 ----------
    if profile is not None:
        # 档案派生的同行人敏感项，仅当对应角色真的在 party 中才生效
        profile_sens = []
        if profile.has_kids and "kid" in intent.party:
            profile_sens.append("孩子友好")
        if profile.has_elderly and "elder" in intent.party:
            profile_sens.append("低强度")
        for sens in profile_sens:
            if sens in _SENS_HARD and not _has_hard(c, _SENS_HARD[sens].field):
                hc = _SENS_HARD[sens]
                c.hard.append(ConstraintItem(hard=hc, source=SOURCE_PROFILE,
                                             reason=f"家庭档案: {hc.label}"))
        for field, val in profile.standing_prefs.items():
            target = val if field in _DIMENSION_FIELDS else None
            c.soft.append(SoftPref(field=field, weight=0.8, source=SOURCE_PROFILE,
                                   reason=f"家庭档案: 长期偏好 {field}={val}", target=target))

    # ---------- 历史学习（飞轮注入） ----------
    # 场景级覆盖优先：scenario_overrides 中出现的字段，在本场景下"替代"全局 user_pref_deltas，
    # 并叠加在模板权重之上以突出加权。
    sc_over = signals.scenario_overrides.get(scenario.id, {})
    override_fields = set(sc_over.keys())

    for field, delta in signals.user_pref_deltas.items():
        if field in override_fields:
            continue  # 本场景下让位给场景级覆盖（scenario_overrides 优先）
        target = getattr(intent, field, None) if field in _DIMENSION_FIELDS else None
        c.soft.append(SoftPref(field=field, weight=delta, source=SOURCE_LEARNED,
                               reason=f"历史学习: 全局用户偏好增量 {field}={delta:+.2f}", target=target))

    for field, delta in sc_over.items():
        target = getattr(intent, field, None) if field in _DIMENSION_FIELDS else None
        c.soft.append(SoftPref(field=field, weight=delta, source=SOURCE_LEARNED,
                               reason=f"历史学习: 场景{scenario.id}覆盖(优先) {field}={delta:+.2f}",
                               target=target))

    return c


def _has_hard(c: Constraint, field: str) -> bool:
    return any(item.hard.field == field for item in c.hard)


def generate_plans(
    intent: IntentFrame,
    scenario: ScenarioTemplate,
    constraint: Constraint,
    signals: Optional[LearnedSignals] = None,
    profile: Optional[Profile] = None,
    repo=None,
) -> List[Plan]:
    """产出全部 activity×restaurant 组合方案，metrics 填好但不排序（排序交给 engine.rank）。

    每个 plan 写入 route_minutes（总通勤）与 per-slot geo。
    """
    repo = repo or get_repository()
    signals = signals or LearnedSignals()
    home = profile.home_geo if profile else "central"

    hard_rules = constraint.hard_rules()
    soft_prefs = constraint.soft
    risk_rules = constraint.risk_rules()

    acts = engine.filter_hard(repo.activities_for(scenario.id), hard_rules)
    ress = engine.filter_hard(repo.restaurants_for(scenario.id), hard_rules)

    plans: List[Plan] = []
    for act in acts:
        for res in ress:
            soft = engine.score_soft(act, soft_prefs) + engine.score_soft(res, soft_prefs)
            # 商家信号（历史学习）：命中则加成
            soft += signals.merchant_signals.get(act.id, 0.0)
            soft += signals.merchant_signals.get(res.id, 0.0)
            # 团购优惠：有券的商户获得与节省额成正比的小幅加成，使含券方案与无券方案产生差异
            soft += _groupbuy_bonus(repo, act.id) + _groupbuy_bonus(repo, res.id)

            risk = engine.apply_risk([act, res], risk_rules)
            route = repo.mock_geo_minutes(home, act.geo) + repo.mock_geo_minutes(act.geo, res.geo)

            slots = [
                _slot("activity", act, repo),
                _slot("meal", res, repo),
            ]
            _assign_windows(slots)
            plan = Plan(
                id=f"{scenario.id}:{act.id}+{res.id}",
                scenario_id=scenario.id,
                slots=slots,
                route_minutes=route,
                soft_score=soft,
                risk_penalty=risk,
                title=f"{scenario.label}·{act.name}+{res.name}",
            )
            plans.append(plan)
    return plans


def select_ab(ranked: List[Plan]) -> List[Plan]:
    """从已排序方案中挑出差异化的 A/B：B 取得分最高、且主活动与 A 不同的方案，
    使两套方案在活动/动线上有明显区分；无可区分项时回退到次高分方案。"""
    if not ranked:
        return []
    a = ranked[0]
    a_act = a.slots[0].ref_id if a.slots else None
    b = next((p for p in ranked[1:] if (p.slots[0].ref_id if p.slots else None) != a_act), None)
    if b is None:
        b = ranked[1] if len(ranked) > 1 else None
    return [a, b] if b is not None else [a]


_GROUPBUY_SAVE_WEIGHT = 0.01   # 每元节省折算的软分加成


def _groupbuy_bonus(repo, merchant_id: str) -> float:
    gb = repo.groupbuy_for(merchant_id)
    return gb.save * _GROUPBUY_SAVE_WEIGHT if gb else 0.0


def _assign_windows(slots: List[PlanSlot], start_hour: int = 10) -> None:
    """为每个 slot 顺序排出时间窗 'HH:MM-HH:MM'（以 10:00 起，按 duration 累加）。"""
    cursor = start_hour * 60
    for s in slots:
        begin, end = cursor, cursor + s.duration_min
        s.window = f"{begin // 60:02d}:{begin % 60:02d}-{end // 60:02d}:{end % 60:02d}"
        cursor = end + 15  # 含 15 分钟缓冲


def _slot(kind: str, item, repo) -> PlanSlot:
    gb = repo.groupbuy_for(item.id)
    return PlanSlot(
        kind=kind,
        ref_id=item.id,
        name=item.name,
        geo=item.geo,
        duration_min=getattr(item, "duration_min", 90),
        groupbuy_id=gb.id if gb else None,
        groupbuy_save=gb.save if gb else 0.0,
    )
