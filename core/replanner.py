"""局部重规划：锁定其余 slot，仅替换受影响的一处，对外暴露 diff。

同时服务 S4 用户反馈与系统兜底（兜底事件由 resource_checker 经 Codex 侧传入，
Step 1 通过 fallback_triggered 入参预留接口）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from models import Plan, PlanSlot, Constraint, LearnedSignals, Profile, SessionState
from core import constraint_engine as engine
from core.planner import _slot, _assign_windows
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


# ---------------------------------------------------------------------------
# 自身状态变更驱动的重规划（单人场景）：无需外部反馈，依据用户自身状态直接触发。
# ---------------------------------------------------------------------------

# 自身状态关键词 → 动作
_SELF_STATE_RULES = [
    ("shorten", ("太累", "累了", "缩短", "取消后面", "后面的活动取消", "不想去了", "早点回", "想回家")),
    ("extend_meal", ("延长用餐", "多坐会", "多坐一会", "再坐会", "慢慢吃", "多待会")),
]

_EXTEND_MINUTES = 30


@dataclass
class SelfStateDiff:
    action: str            # shorten / extend_meal
    trigger: str           # 命中的自身状态短语
    detail: str            # 人类可读变更说明
    delta_route_minutes: int
    locked: List[str]      # 保留（锁定）的 slot 名称

    def describe(self) -> str:
        return (f"[自身状态·{self.action}] «{self.trigger}» → {self.detail} "
                f"(保留: {', '.join(self.locked)}) Δroute={self.delta_route_minutes:+d}min")


def detect_self_state(text: str) -> Optional[str]:
    """从用户自述文本判定自身状态动作；无命中返回 None。"""
    for action, kws in _SELF_STATE_RULES:
        for kw in kws:
            if kw in (text or ""):
                return action
    return None


def replan_on_self_state(
    session: SessionState,
    self_state_text: str,
    profile: Optional[Profile] = None,
    repo=None,
):
    """单人场景：当 SessionState 侦测到用户自身状态变化时，无需外部反馈直接重规划。

    返回 (new_plan, SelfStateDiff)。同时把结果写回 session.current_plan，
    并将 current_exec_state 置为 'replanned'。无可执行动作时返回 (current_plan, None)。
    """
    repo = repo or get_repository()
    plan = session.current_plan
    if plan is None:
        return None, None

    action = detect_self_state(self_state_text)
    if action is None:
        return plan, None

    home = profile.home_geo if profile else "central"

    if action == "shorten":
        new_plan, diff = _shorten(plan, self_state_text, repo, home)
    elif action == "extend_meal":
        new_plan, diff = _extend_meal(plan, self_state_text)
    else:
        return plan, None

    session.current_plan = new_plan
    session.current_exec_state = "replanned"
    return new_plan, diff


def _shorten(plan: Plan, trigger: str, repo, home: str):
    """缩短行程：取消首个之后的所有 slot（保留主活动/首项），重算动线与时间窗。"""
    if len(plan.slots) <= 1:
        return plan, None
    kept = [plan.slots[0]]
    dropped = [s.name for s in plan.slots[1:]]

    new_slots = [PlanSlot(**{k: getattr(kept[0], k) for k in (
        "kind", "ref_id", "name", "geo", "duration_min", "groupbuy_id",
        "groupbuy_save", "slot_id", "window")})]
    _assign_windows(new_slots)
    route = repo.mock_geo_minutes(home, new_slots[0].geo)

    new_plan = Plan(
        id=f"{plan.id}|self:shorten",
        scenario_id=plan.scenario_id,
        slots=new_slots,
        route_minutes=route,
        soft_score=plan.soft_score,
        risk_penalty=plan.risk_penalty,
        title=plan.title,
        locked_items=[new_slots[0].slot_id],
        flexible_items=[],
        notes=list(plan.notes) + [f"自身状态缩短：取消 {', '.join(dropped)}"],
    )
    engine.rank([new_plan], use_route_weight=True)
    diff = SelfStateDiff(
        action="shorten", trigger=trigger.strip(),
        detail=f"取消 {', '.join(dropped)}，仅保留 {new_slots[0].name}",
        delta_route_minutes=route - plan.route_minutes,
        locked=[new_slots[0].name],
    )
    return new_plan, diff


def _extend_meal(plan: Plan, trigger: str):
    """延长用餐：增加 meal slot 时长，顺延后续时间窗，动线不变。"""
    new_slots = [PlanSlot(**{k: getattr(s, k) for k in (
        "kind", "ref_id", "name", "geo", "duration_min", "groupbuy_id",
        "groupbuy_save", "slot_id", "window")}) for s in plan.slots]
    target = next((s for s in new_slots if s.kind == "meal"), None)
    if target is None:
        return plan, None
    target.duration_min += _EXTEND_MINUTES
    _assign_windows(new_slots)

    new_plan = Plan(
        id=f"{plan.id}|self:extend_meal",
        scenario_id=plan.scenario_id,
        slots=new_slots,
        route_minutes=plan.route_minutes,
        soft_score=plan.soft_score,
        risk_penalty=plan.risk_penalty,
        title=plan.title,
        locked_items=[s.slot_id for s in new_slots],
        flexible_items=[],
        notes=list(plan.notes) + [f"自身状态延长用餐 +{_EXTEND_MINUTES} 分钟"],
    )
    engine.rank([new_plan], use_route_weight=True)
    diff = SelfStateDiff(
        action="extend_meal", trigger=trigger.strip(),
        detail=f"{target.name} 用餐延长 +{_EXTEND_MINUTES} 分钟，后续时间窗顺延",
        delta_route_minutes=0,
        locked=[s.name for s in new_slots],
    )
    return new_plan, diff


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
