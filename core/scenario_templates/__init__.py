"""四场景模板注册表。"""

from __future__ import annotations

from models import ScenarioTemplate

from . import family, friend, date, solo

_BUILDERS = {
    "family": family.build_template,
    "friend": friend.build_template,
    "date": date.build_template,
    "solo": solo.build_template,
}


def build(scenario_id: str) -> ScenarioTemplate:
    return _BUILDERS[scenario_id]()


def all_ids():
    return list(_BUILDERS.keys())
