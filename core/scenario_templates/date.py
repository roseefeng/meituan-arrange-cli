from __future__ import annotations

from models import ScenarioTemplate, HardConstraint, RiskRule


def build_template() -> ScenarioTemplate:
    return ScenarioTemplate(
        id="date",
        label="约会",
        base_constraints=[
            HardConstraint("kid_friendly", "ne", True, label="非亲子定位（约会）"),
        ],
        weight_overrides={
            "photogenic": 1.8,         # 出片/氛围为首要项
            "vibe": 1.0,
            "meal_focus": 1.0,
            "setting": 0.6,
            "spend": 0.6,
        },
        risk_extras=[
            RiskRule("date-too-noisy", "vibe", "eq", "热闹", penalty=0.8,
                     label="过吵闹对约会氛围扣分"),
        ],
    )
