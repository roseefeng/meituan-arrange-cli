from __future__ import annotations

from models import ScenarioTemplate, HardConstraint, RiskRule


def build_template() -> ScenarioTemplate:
    """单人场景模板。

    - base_constraints：单人友好 / 不尴尬就餐 / 晚归安全。
    - weight_overrides：vibe·effort·spend·meal_focus 全部归到用户单人偏好，去掉多人平衡项。
    - risk_extras：晚间单人安全扣分。
    """
    return ScenarioTemplate(
        id="solo",
        label="一个人",
        base_constraints=[
            HardConstraint("solo_friendly", "true", True, label="单人友好/不尴尬就餐"),
        ],
        weight_overrides={
            # 全部归到用户单人偏好；无 kid_balance / group_lively 等多人平衡项
            "solo_pref": 1.5,
            "vibe": 1.2,
            "effort": 1.2,
            "spend": 1.2,
            "meal_focus": 1.2,
        },
        risk_extras=[
            RiskRule("solo-night-safety", "setting", "eq", "室外", penalty=1.5,
                     label="晚间单人户外安全扣分"),
        ],
    )
