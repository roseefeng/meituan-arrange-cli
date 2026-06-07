from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .intent import IntentFrame


@dataclass
class RunRecord:
    """一次完整运行的留痕。fallback_triggered 为新增字段（来源 = 本次增补）。"""

    id: str
    ts: str
    intent: Optional[IntentFrame] = None
    chosen_plan_id: Optional[str] = None
    feedback: Optional[str] = None
    replanned: bool = False
    signals_emitted: List[str] = field(default_factory=list)
    fallback_triggered: bool = False     # 新增字段：是否由系统兜底触发
