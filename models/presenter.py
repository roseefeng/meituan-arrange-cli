"""输出模式边界：user（默认）与 verbose（--verbose）。

纯格式化层，覆盖在数据契约之上。强约束：
- user 模式只产出四项：basis / reassurance / reversible_funds / locked_variable。
- verbose 模式在 user 四项之外，附加候选池、淘汰商家及原因、原始分、tool I/O、信号细节。
- user 模式严禁泄露任何 verbose 字段。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .plan import Plan
from .constraint import Constraint

# user 模式允许的顶层键（白名单，渲染前后均可据此校验）
USER_KEYS = ("basis", "reassurance", "reversible_funds", "locked_variable")
# verbose 模式额外键
VERBOSE_EXTRA_KEYS = (
    "candidate_pool", "rejected_merchants", "raw_scores", "signal_injection", "tool_io",
)


def _slot_name(plan: Plan, slot_id: str) -> str:
    for s in plan.slots:
        if s.slot_id == slot_id:
            return s.name
    return slot_id


def _locked_flexible(plan: Plan):
    """确定项 / 可调项：优先用 plan 显式 locked/flexible；否则以"是否已下团购券"近似。"""
    if plan.locked_items or plan.flexible_items:
        locked = [_slot_name(plan, sid) for sid in plan.locked_items]
        flexible = [_slot_name(plan, sid) for sid in plan.flexible_items]
        if locked or flexible:
            return locked, flexible
    locked = [s.name for s in plan.slots if s.groupbuy_id]
    flexible = [s.name for s in plan.slots if not s.groupbuy_id]
    return locked, flexible


def render_user(plan: Plan, constraint: Optional[Constraint] = None,
                max_basis: int = 6) -> Dict:
    """user 模式：仅四项。"""
    # 安排依据：取自约束 reason（去重保序）
    basis: List[str] = []
    if constraint is not None:
        seen = set()
        for item in list(constraint.hard) + list(constraint.soft) + list(constraint.risk):
            r = item.reason
            if r and r not in seen:
                seen.add(r)
                basis.append(r)
    basis = basis[:max_basis]

    locked, flexible = _locked_flexible(plan)

    refundable = [
        {"item": s.name, "groupbuy": s.groupbuy_id, "save": s.groupbuy_save}
        for s in plan.slots if s.groupbuy_id
    ]

    reassurance: List[str] = [
        "可逆：未锁定项支持一键改期/替换，方案 B 已备选。",
        "资金安全：团购券未核销支持随时退，未消费全额退款。" if refundable
        else "资金安全：到店现结，无预付资金占用。",
    ]

    reversible_funds = {
        "locked": locked,                 # 已确定/已下单
        "adjustable": flexible,           # 可退改
        "refundable_groupbuys": refundable,
    }

    locked_variable = {
        "locked": locked,                 # 确定不变
        "flexible": flexible,             # 可调整
    }

    return {
        "basis": basis,
        "reassurance": reassurance,
        "reversible_funds": reversible_funds,
        "locked_variable": locked_variable,
    }


def render_verbose(
    plan: Plan,
    constraint: Optional[Constraint] = None,
    candidate_pool: Optional[List] = None,
    rejected_merchants: Optional[List[Dict]] = None,
    signals=None,
    tool_io: Optional[List] = None,
) -> Dict:
    """verbose 模式：user 四项 + 调试细节。"""
    view = render_user(plan, constraint)
    view["candidate_pool"] = list(candidate_pool or [])
    # 淘汰商家及原因：优先用显式传入，否则取 plan.rejected_merchants
    if rejected_merchants is not None:
        view["rejected_merchants"] = rejected_merchants
    else:
        view["rejected_merchants"] = [
            {"merchant_id": m, "reason": "兜底/资源校验淘汰"} for m in plan.rejected_merchants
        ]
    view["raw_scores"] = {
        "soft_score": plan.soft_score,
        "risk_penalty": plan.risk_penalty,
        "route_minutes": plan.route_minutes,
        "total_score": plan.total_score,
        "score": plan.score,
    }
    if signals is not None:
        view["signal_injection"] = {
            "user_pref_deltas": dict(getattr(signals, "user_pref_deltas", {})),
            "merchant_signals": dict(getattr(signals, "merchant_signals", {})),
            "scenario_overrides": dict(getattr(signals, "scenario_overrides", {})),
        }
    else:
        view["signal_injection"] = {}
    view["tool_io"] = list(tool_io or [])
    return view


def assert_user_safe(view: Dict) -> None:
    """守卫：user 模式输出不得包含任何 verbose 字段。"""
    leaked = [k for k in view.keys() if k not in USER_KEYS]
    if leaked:
        raise AssertionError(f"user 模式泄露 verbose 字段: {leaked}")


def format_user(view: Dict) -> str:
    lines = ["【安排依据】"]
    lines += [f"  - {b}" for b in view["basis"]]
    lines.append("【安心理由】")
    lines += [f"  - {r}" for r in view["reassurance"]]
    rf = view["reversible_funds"]
    lines.append("【可逆-资金拆分】")
    lines.append(f"  已确定/已下单: {rf['locked'] or '无'}")
    lines.append(f"  可退改: {rf['adjustable'] or '无'}")
    if rf["refundable_groupbuys"]:
        lines.append("  可退团购券: " + ", ".join(
            f"{g['item']}({g['groupbuy']} 省{g['save']:.0f})" for g in rf["refundable_groupbuys"]))
    lv = view["locked_variable"]
    lines.append("【锁定-变动项】")
    lines.append(f"  锁定(确定): {lv['locked'] or '无'}")
    lines.append(f"  变动(可调): {lv['flexible'] or '无'}")
    return "\n".join(lines)


def format_verbose(view: Dict) -> str:
    out = [format_user({k: view[k] for k in USER_KEYS})]
    out.append("【候选池】 " + ", ".join(str(c) for c in view.get("candidate_pool", [])))
    rej = view.get("rejected_merchants", [])
    out.append("【淘汰商家及原因】 " + (
        "; ".join(f"{r.get('merchant_id')}:{r.get('reason')}" for r in rej) if rej else "无"))
    rs = view.get("raw_scores", {})
    out.append(f"【原始分】 soft={rs.get('soft_score', 0):.2f} risk={rs.get('risk_penalty', 0):.2f} "
               f"route={rs.get('route_minutes')}min total={rs.get('total_score', 0):.2f}")
    out.append(f"【信号注入/产出】 {view.get('signal_injection', {})}")
    out.append(f"【tool I/O】 {view.get('tool_io', [])}")
    return "\n".join(out)
