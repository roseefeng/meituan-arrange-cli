from __future__ import annotations

from models import ScenarioTemplate, HardConstraint, RiskRule


def build_template() -> ScenarioTemplate:
    return ScenarioTemplate(
        id="friend",
        label="朋友聚会",
        base_constraints=[
            HardConstraint("kid_friendly", "ne", True, label="非亲子定位（朋友局）"),
        ],
        weight_overrides={
            "group_lively": 2.0,       # 多人热闹平衡为首要项
            "vibe": 1.0,
            "meal_focus": 1.0,
            "spend": 0.8,
            "effort": 0.5,
        },
        risk_extras=[
            RiskRule("friend-too-quiet", "vibe", "eq", "松弛", penalty=0.5,
                     label="过于安静对朋友局扣分"),
        ],
    )
