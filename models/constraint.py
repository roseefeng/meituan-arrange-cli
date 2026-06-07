from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .scenario import HardConstraint, RiskRule

# 约束来源标签（每条约束 reason 必带其一）
SOURCE_GOAL = "本次目标"
SOURCE_PROFILE = "家庭档案"
SOURCE_LEARNED = "历史学习"


@dataclass
class ConstraintItem:
    """带来源的硬约束包装。"""

    hard: HardConstraint
    source: str
    reason: str


@dataclass
class SoftPref:
    """带来源与权重的软偏好。target 为期望取值（来自意图），无目标值的结构性偏好为 None。"""

    field: str
    weight: float
    source: str
    reason: str
    target: object = None


@dataclass
class RiskItem:
    rule: RiskRule
    source: str
    reason: str


@dataclass
class Constraint:
    """build_constraints 的产物：三类约束 + 来源标签的统一容器。"""

    hard: List[ConstraintItem] = field(default_factory=list)
    soft: List[SoftPref] = field(default_factory=list)
    risk: List[RiskItem] = field(default_factory=list)

    def hard_rules(self) -> List[HardConstraint]:
        return [c.hard for c in self.hard]

    def soft_weights(self) -> dict:
        # 同字段多来源叠加
        out: dict = {}
        for s in self.soft:
            out[s.field] = out.get(s.field, 0.0) + s.weight
        return out

    def risk_rules(self) -> List[RiskRule]:
        return [r.rule for r in self.risk]

    def source_breakdown(self) -> dict:
        counts = {SOURCE_GOAL: 0, SOURCE_PROFILE: 0, SOURCE_LEARNED: 0}
        for item in list(self.hard) + list(self.soft) + list(self.risk):
            counts[item.source] = counts.get(item.source, 0) + 1
        return counts
