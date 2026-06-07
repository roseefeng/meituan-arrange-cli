from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Profile:
    """用户/家庭档案。作为 parser 与 router 的兜底信号来源（来源标签 = 家庭档案）。"""

    user_id: str = "u_demo"
    home_geo: str = "central"
    default_party: List[str] = field(default_factory=list)   # 档案常驻同行人，如 ["kid"], ["partner"]
    has_kids: bool = False
    has_elderly: bool = False
    standing_prefs: Dict[str, str] = field(default_factory=dict)   # 长期偏好，如 {"spend": "省"}

    def derived_sensitivities(self) -> List[str]:
        out: List[str] = []
        if self.has_kids:
            out.append("孩子友好")
        if self.has_elderly:
            out.append("低强度")
        return out
