"""飞轮：LearnedSignals 读写。开局注入 Planner，会话末产出 delta + 商家信号。"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import List, Optional

from models import LearnedSignals, RunRecord, IntentFrame, Plan
from mock.repository import LEARNED_SIGNALS_PATH

_DIMENSION_FIELDS = {"vibe", "setting", "effort", "spend", "meal_focus"}
_PREF_STEP = 0.2          # 正反馈对维度偏好的增量
_MERCHANT_STEP = 0.5      # 正反馈对商家信号的增量


class Flywheel:
    def __init__(self, path: str = LEARNED_SIGNALS_PATH):
        self.path = path

    # ---------- 开局：读取并注入 ----------
    def load(self) -> LearnedSignals:
        if not os.path.exists(self.path):
            return LearnedSignals()
        with open(self.path, "r", encoding="utf-8") as f:
            return LearnedSignals.from_dict(json.load(f))

    def save(self, signals: LearnedSignals) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(signals.to_dict(), f, ensure_ascii=False, indent=2)

    # ---------- 会话末：产出 delta + 商家信号 ----------
    def emit(
        self,
        signals: LearnedSignals,
        intent: IntentFrame,
        scenario_id: str,
        chosen_plan: Optional[Plan],
        feedback: str = "like",
        replanned: bool = False,
        fallback_triggered: bool = False,
        persist: bool = True,
    ):
        """根据反馈更新 LearnedSignals，返回 (updated_signals, RunRecord)。"""
        emitted: List[str] = []
        direction = 1.0 if feedback in ("like", "good", "positive") else -1.0

        # 维度偏好增量
        for field in _DIMENSION_FIELDS:
            if getattr(intent, field, None) is not None:
                cur = signals.user_pref_deltas.get(field, 0.0)
                signals.user_pref_deltas[field] = round(cur + direction * _PREF_STEP, 3)
                emitted.append(f"user_pref:{field}{direction * _PREF_STEP:+.2f}")

        # 场景级增量（强化该场景的首要权重字段）
        if chosen_plan is not None:
            over = signals.scenario_overrides.setdefault(scenario_id, {})
            key = _scenario_emphasis(scenario_id)
            over[key] = round(over.get(key, 0.0) + direction * _PREF_STEP, 3)
            emitted.append(f"scenario[{scenario_id}]:{key}{direction * _PREF_STEP:+.2f}")

            # 商家信号
            for slot in chosen_plan.slots:
                cur = signals.merchant_signals.get(slot.ref_id, 0.0)
                signals.merchant_signals[slot.ref_id] = round(cur + direction * _MERCHANT_STEP, 3)
                emitted.append(f"merchant:{slot.ref_id}{direction * _MERCHANT_STEP:+.2f}")

        signals.last_updated = datetime.now(timezone.utc).isoformat()

        record = RunRecord(
            id=f"run-{int(datetime.now(timezone.utc).timestamp())}",
            ts=signals.last_updated,
            intent=intent,
            chosen_plan_id=chosen_plan.id if chosen_plan else None,
            feedback=feedback,
            replanned=replanned,
            signals_emitted=emitted,
            fallback_triggered=fallback_triggered,
        )

        if persist:
            self.save(signals)
        return signals, record


def _scenario_emphasis(scenario_id: str) -> str:
    return {
        "family": "kid_balance",
        "friend": "group_lively",
        "date": "photogenic",
        "solo": "solo_pref",
    }.get(scenario_id, "vibe")
