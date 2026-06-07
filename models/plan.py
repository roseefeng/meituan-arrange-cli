from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PlanSlot:
    """方案中的一个时段。geo 为新增字段（来源 = 本次增补）。"""

    kind: str              # activity / meal
    ref_id: str
    name: str
    geo: str               # per-slot geo（新增字段）
    duration_min: int = 90
    groupbuy_id: Optional[str] = None
    groupbuy_save: float = 0.0


@dataclass
class Plan:
    """一套安排。route_minutes 与 per-slot geo 为新增字段（来源 = 本次增补）。"""

    id: str
    scenario_id: str
    slots: List[PlanSlot] = field(default_factory=list)
    route_minutes: int = 0          # 总通勤（新增字段）
    soft_score: float = 0.0
    risk_penalty: float = 0.0
    total_score: float = 0.0
    notes: List[str] = field(default_factory=list)

    def geo_path(self) -> List[str]:
        return [s.geo for s in self.slots]

    def summary(self) -> str:
        path = " → ".join(f"{s.name}@{s.geo}" for s in self.slots)
        return (
            f"[{self.id}] {path} | route={self.route_minutes}min "
            f"soft={self.soft_score:.2f} risk=-{self.risk_penalty:.2f} total={self.total_score:.2f}"
        )
