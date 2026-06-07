from __future__ import annotations

from models import ScenarioTemplate, HardConstraint, RiskRule


def build_template() -> ScenarioTemplate:
    return ScenarioTemplate(
        id="family",
        label="家庭出行",
        base_constraints=[
            HardConstraint("kid_friendly", "true", True, label="亲子友好场所"),
        ],
        weight_overrides={
            "kid_balance": 2.0,        # 亲子平衡为首要项
            "low_intensity": 1.2,
            "spend": 1.0,
            "meal_focus": 1.0,
            "setting": 0.8,
            "vibe": 0.5,
        },
        risk_extras=[
            RiskRule("family-high-intensity", "low_intensity", "false", penalty=1.0,
                     label="高强度活动对亲子扣分"),
        ],
    )
