from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class HardConstraint:
    """硬约束：候选不满足即被 filter_hard 淘汰。"""

    field: str          # 候选实体上的属性名，如 "kid_friendly" / "low_cal" / "solo_friendly"
    op: str             # eq / ne / true / false / in / contains
    value: object = None
    label: str = ""     # 人类可读说明，进入 reason

    def describe(self) -> str:
        return self.label or f"{self.field} {self.op} {self.value}"


@dataclass
class RiskRule:
    """风险扣分规则：命中则对 plan/候选施加 penalty。"""

    name: str
    field: str          # 被检查的属性
    op: str             # true / false / eq / ne / gt
    value: object = None
    penalty: float = 1.0
    label: str = ""

    def describe(self) -> str:
        return self.label or f"{self.name}({self.field} {self.op} {self.value} → -{self.penalty})"


@dataclass
class ScenarioTemplate:
    """场景模板：硬约束基线 + 软权重覆盖 + 风险增项。"""

    id: str             # family / friend / date / solo
    label: str
    base_constraints: List[HardConstraint] = field(default_factory=list)
    weight_overrides: Dict[str, float] = field(default_factory=dict)   # field -> weight
    risk_extras: List[RiskRule] = field(default_factory=list)
