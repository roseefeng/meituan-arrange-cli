from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PlanSlot:
    """方案中的一个时段。

    对外契约字段：slot_id, name, geo, window。
    内部/兼容字段：kind, ref_id, duration_min, groupbuy_id, groupbuy_save。
    geo 为新增字段（来源 = 本次增补）。
    """

    kind: str              # activity / meal
    ref_id: str
    name: str
    geo: str               # per-slot geo（新增字段）
    duration_min: int = 90
    groupbuy_id: Optional[str] = None
    groupbuy_save: float = 0.0
    slot_id: str = ""      # 对外契约：稳定的 slot 标识（默认取 ref_id）
    window: str = ""       # 对外契约：时间窗 "HH:MM-HH:MM"

    def __post_init__(self):
        if not self.slot_id:
            self.slot_id = self.ref_id


@dataclass
class Plan:
    """一套安排。

    对外契约字段：plan_id, title, route_minutes, slots, locked_items,
    flexible_items, score, rejected_merchants。
    内部/兼容字段：id, scenario_id, soft_score, risk_penalty, total_score, notes。
    route_minutes 与 per-slot geo 为新增字段（来源 = 本次增补）。
    """

    id: str
    scenario_id: str
    slots: List[PlanSlot] = field(default_factory=list)
    route_minutes: int = 0          # 总通勤（新增字段）
    soft_score: float = 0.0
    risk_penalty: float = 0.0
    total_score: float = 0.0
    notes: List[str] = field(default_factory=list)
    # 对外契约字段
    plan_id: str = ""               # 默认取 id
    title: str = ""
    locked_items: List[str] = field(default_factory=list)     # 锁定的 slot_id（重规划用）
    flexible_items: List[str] = field(default_factory=list)   # 可替换的 slot_id
    score: float = 0.0              # 对外评分（镜像 total_score）
    rejected_merchants: List[str] = field(default_factory=list)  # 兜底/资源校验淘汰的 merchant_id

    def __post_init__(self):
        if not self.plan_id:
            self.plan_id = self.id
        if not self.flexible_items:
            self.flexible_items = [s.slot_id for s in self.slots]

    def geo_path(self) -> List[str]:
        return [s.geo for s in self.slots]

    def summary(self) -> str:
        path = " → ".join(f"{s.name}@{s.geo}" for s in self.slots)
        return (
            f"[{self.id}] {path} | route={self.route_minutes}min "
            f"soft={self.soft_score:.2f} risk=-{self.risk_penalty:.2f} total={self.total_score:.2f}"
        )
