from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class LearnedSignals:
    """飞轮学习信号。开局注入 Planner，会话末回写。"""

    user_pref_deltas: Dict[str, float] = field(default_factory=dict)        # field -> 软权重增量
    merchant_signals: Dict[str, float] = field(default_factory=dict)        # merchant_id -> 偏好增量
    scenario_overrides: Dict[str, dict] = field(default_factory=dict)       # scenario_id -> {field: delta}
    last_updated: str = ""

    def to_dict(self) -> dict:
        return {
            "user_pref_deltas": self.user_pref_deltas,
            "merchant_signals": self.merchant_signals,
            "scenario_overrides": self.scenario_overrides,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LearnedSignals":
        return cls(
            user_pref_deltas=dict(d.get("user_pref_deltas", {})),
            merchant_signals=dict(d.get("merchant_signals", {})),
            scenario_overrides=dict(d.get("scenario_overrides", {})),
            last_updated=d.get("last_updated", ""),
        )

    def is_empty(self) -> bool:
        return not (self.user_pref_deltas or self.merchant_signals or self.scenario_overrides)
