from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class IntentFrame:
    """一次诉求的结构化意图。fired_rules 记录命中的规则名与文本 span，便于可解释回放。"""

    raw_goal: str
    vibe: Optional[str] = None            # 松弛 / 热闹 / 文艺 / 出片
    setting: Optional[str] = None         # 室内 / 室外 / 商场 / 公园
    effort: Optional[str] = None          # 躺平 / 轻度 / 能折腾
    spend: Optional[str] = None           # 省 / 适中 / 不在乎
    meal_focus: Optional[str] = None      # 正餐 / 小吃 / 咖啡 / 不重要
    duration_hint: Optional[str] = None   # 短 / 半天 / 全天
    sensitivities: List[str] = field(default_factory=list)   # 减脂 / 忌辣 / 孩子友好 / 不能久走 ...
    party: List[str] = field(default_factory=list)           # [user] / [user, kid] / [user, partner] ...
    fired_rules: List[Tuple[str, Tuple[int, int]]] = field(default_factory=list)  # (name, (start, end))

    def summary(self) -> str:
        bits = [
            f"vibe={self.vibe}",
            f"setting={self.setting}",
            f"effort={self.effort}",
            f"spend={self.spend}",
            f"meal={self.meal_focus}",
            f"dur={self.duration_hint}",
            f"sens={self.sensitivities}",
            f"party={self.party}",
        ]
        return ", ".join(bits)
