"""局部重规划：锁定其余 slot，仅替换受影响的一处，对外暴露 diff。

同时服务 S4 用户反馈与系统兜底（兜底事件由 resource_checker 经 Codex 侧传入，
Step 1 通过 fallback_triggered 入参预留接口）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from models import Plan, PlanSlot, Constraint, LearnedSignals, Profile
from core import constraint_engine as engine
from core.planner import _slot
from mock.repository import get_repository


@dataclass
class ReplanDiff:
    slot_index: int
    field_from: str
    field_to: str
    locked: List[str]
    fallback_triggered: bool
    delta_route_minutes: int
    delta_total: float

    def describe(self) -> str:
        tag = "兜底" if self.fallback_triggered else "用户反馈"
        return (
            f"[{tag}] slot#{self.slot_index}: {self.field_from} → {self.field_to} "
            f"(锁定: {', '.join(self.locked)}) "
            f"Δroute={self.delta_route_minutes:+d}min Δtotal={self.delta_total:+.2f}"
        )


def replan(
    plan: Plan,
    slot_index: int,
    constraint: Constraint,
    signals: Optional[LearnedSignals] = None,
    profile: Optional[Profile] = None,
    repo=None,
    fallback_triggered: bool = False,
    exclude_ids: Optional[List[str]] = None,
):
    """返回 (new_plan, ReplanDiff)。仅替换 slot_index 处，其余 slot 锁定。"""
    repo = repo or get_repository()
    signals = signals or LearnedSignals()
    exclude_ids = set(exclude_ids or [])
    home = profile.home_geo if profile else "central"

    target_slot = plan.slots[slot_index]
    exclude_ids.add(target_slot.ref_id)

    hard_rules = constraint.hard_rules()
    soft_prefs = constraint.soft
    risk_rules = constraint.risk_rules()

    if target_slot.kind == "activity":
        pool = repo.activities_for(plan.scenario_id)
    else:
        pool = repo.restaurants_for(plan.scenario_id)
    candidates = [c for c in engine.filter_hard(pool, hard_rules) if c.id not in exclude_ids]

    if not candidates:
        return None, None

    best_plan = None
    best_cand = None
    for cand in candidates:
        trial = _swap(plan, slot_index, cand, repo, home, soft_prefs, risk_rules, signals)
        if best_plan is None or trial.total_score > best_plan.total_score:
            best_plan = trial
            best_cand = cand

    # 记录锁定项与（兜底场景下）被淘汰商家，供 RunRecord/flywheel 使用
    best_plan.locked_items = [s.slot_id for i, s in enumerate(plan.slots) if i != slot_index]
    best_plan.flexible_items = [plan.slots[slot_index].slot_id]
    if fallback_triggered:
        best_plan.rejected_merchants = [target_slot.ref_id]

    locked = [s.name for i, s in enumerate(plan.slots) if i != slot_index]
    diff = ReplanDiff(
        slot_index=slot_index,
        field_from=target_slot.name,
        field_to=best_cand.name,
        locked=locked,
        fallback_triggered=fallback_triggered,
        delta_route_minutes=best_plan.route_minutes - plan.route_minutes,
        delta_total=best_plan.total_score - plan.total_score,
    )
    return best_plan, diff


def _swap(plan, slot_index, cand, repo, home, soft_prefs, risk_rules, signals) -> Plan:
    new_slots: List[PlanSlot] = list(plan.slots)
    new_slots[slot_index] = _slot(plan.slots[slot_index].kind, cand, repo)

    # 重算动线（按 home → slot0 → slot1 ... 顺序累加）
    route = repo.mock_geo_minutes(home, new_slots[0].geo)
    for i in range(len(new_slots) - 1):
        route += repo.mock_geo_minutes(new_slots[i].geo, new_slots[i + 1].geo)

    # 重算软分与风险（用 slot 对应的候选实体）
    items = [_resolve(s, repo) for s in new_slots]
    soft = sum(engine.score_soft(it, soft_prefs) for it in items)
    for it in items:
        soft += signals.merchant_signals.get(it.id, 0.0)
    risk = engine.apply_risk(items, risk_rules)

    new_plan = Plan(
        id=f"{plan.id}|replan@{slot_index}={cand.id}",
        scenario_id=plan.scenario_id,
        slots=new_slots,
        route_minutes=route,
        soft_score=soft,
        risk_penalty=risk,
    )
    engine.rank([new_plan], use_route_weight=True)  # 写入 total_score
    return new_plan


def _resolve(slot: PlanSlot, repo):
    if slot.kind == "activity":
        for a in repo.activities:
            if a.id == slot.ref_id:
                return a
    else:
        for r in repo.restaurants:
            if r.id == slot.ref_id:
                return r
    raise KeyError(slot.ref_id)
