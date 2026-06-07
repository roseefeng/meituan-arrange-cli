"""数据契约层：所有跨模块传递的结构体。

字段定义为冻结契约（见 prompt）。仅在"协商新增字段"范围内扩展。
"""

from .intent import IntentFrame
from .profile import Profile
from .scenario import ScenarioTemplate, HardConstraint, RiskRule
from .constraint import Constraint, ConstraintItem, SoftPref, RiskItem, SOURCE_GOAL, SOURCE_PROFILE, SOURCE_LEARNED
from .plan import Plan, PlanSlot
from .signals import LearnedSignals
from .session import SessionState
from .record import RunRecord
from .catalog import Activity, Restaurant, GroupBuy

__all__ = [
    "IntentFrame",
    "Profile",
    "ScenarioTemplate",
    "HardConstraint",
    "RiskRule",
    "Constraint",
    "ConstraintItem",
    "SoftPref",
    "RiskItem",
    "SOURCE_GOAL",
    "SOURCE_PROFILE",
    "SOURCE_LEARNED",
    "Plan",
    "PlanSlot",
    "LearnedSignals",
    "SessionState",
    "RunRecord",
    "Activity",
    "Restaurant",
    "GroupBuy",
]
