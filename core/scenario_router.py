"""场景路由：IntentFrame.party → ScenarioTemplate。

party 长度为 1（仅 user）时选中 solo。其余按角色优先级 family > date > friend。
"""

from __future__ import annotations

from typing import Optional

from models import IntentFrame, Profile, ScenarioTemplate
from core import scenario_templates

_ROLE_TO_SCENARIO = {
    "kid": "family",
    "elder": "family",
    "family": "family",
    "partner": "date",
    "friends": "friend",
}

_PRIORITY = {"family": 3, "date": 2, "friend": 1, "solo": 0}


def route(intent: IntentFrame, profile: Optional[Profile] = None) -> ScenarioTemplate:
    co_roles = [r for r in intent.party if r != "user"]

    if not co_roles:
        scenario_id = "solo"
    else:
        candidates = {_ROLE_TO_SCENARIO.get(r, "friend") for r in co_roles}
        scenario_id = max(candidates, key=lambda s: _PRIORITY[s])

    return scenario_templates.build(scenario_id)
