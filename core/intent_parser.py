"""raw_goal → IntentFrame。fired_rules 记录命中规则名与文本 span，支撑可解释回放。"""

from __future__ import annotations

from typing import Optional

from models import IntentFrame, Profile
from core import intent_ontology as onto


def parse(raw_goal: str, profile: Optional[Profile] = None) -> IntentFrame:
    text = raw_goal or ""
    frame = IntentFrame(raw_goal=raw_goal)

    # 六维 + 敏感项
    for rule in onto.DIMENSION_RULES:
        span = onto.find_first_span(text, rule.keywords)
        if span is None:
            continue
        frame.fired_rules.append((rule.name, span))
        if rule.dimension == onto.SENSITIVITY:
            if rule.value not in frame.sensitivities:
                frame.sensitivities.append(rule.value)
        else:
            # 单值维度：首个命中生效，后续仅记录不覆盖
            if getattr(frame, rule.dimension) is None:
                setattr(frame, rule.dimension, rule.value)

    # party 解析
    roles: list = []
    for prule in onto.PARTY_RULES:
        span = onto.find_first_span(text, prule.keywords)
        if span is None:
            continue
        frame.fired_rules.append((prule.name, span))
        if prule.role not in roles:
            roles.append(prule.role)

    # 同行人去掉 solo 的 user 占位后判断
    co_roles = [r for r in roles if r != "user"]
    if not co_roles:
        # 文本无同行人：看档案兜底
        if profile and profile.default_party:
            co_roles = list(profile.default_party)
        # 仍无 → 单人
    party = ["user"] + co_roles
    # 去重保持顺序
    seen = set()
    frame.party = [r for r in party if not (r in seen or seen.add(r))]

    # 孩子/老人在 party 里时，补齐对应敏感项（来源仍归本次目标，因来自文本/同行结构）
    if any(r in ("kid",) for r in frame.party) and "孩子友好" not in frame.sensitivities:
        frame.sensitivities.append("孩子友好")
    if any(r in ("elder",) for r in frame.party) and "低强度" not in frame.sensitivities:
        frame.sensitivities.append("低强度")

    return frame
