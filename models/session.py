from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .intent import IntentFrame
from .plan import Plan
from .signals import LearnedSignals


@dataclass
class SessionState:
    """单次会话的运行态快照。"""

    current_intent: Optional[IntentFrame] = None
    current_plan: Optional[Plan] = None
    current_exec_state: str = "idle"     # idle / planned / replanned / done
    scenario_id: Optional[str] = None
    signals_snapshot: Optional[LearnedSignals] = None
    candidate_plans: List[Plan] = field(default_factory=list)
