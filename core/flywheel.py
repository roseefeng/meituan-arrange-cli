"""飞轮：LearnedSignals 读写。开局注入 Planner，会话末产出 delta + 商家信号。"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import List, Optional

# 定义真源在 models/，此处再导出，使 `from core.flywheel import ...` 可用
from models import LearnedSignals, RunRecord, IntentFrame, Plan, SessionState  # noqa: F401
from mock.repository import LEARNED_SIGNALS_PATH, RUNS_PATH

_DIMENSION_FIELDS = {"vibe", "setting", "effort", "spend", "meal_focus"}
_PREF_STEP = 0.2          # 正反馈对全局维度偏好的增量
_OVERRIDE_STEP = 0.4      # 正反馈对场景级维度覆盖的增量（场景优先，权重更显著）
_MERCHANT_STEP = 0.5      # 正反馈对商家信号的增量
_FALLBACK_STEP = 0.3      # 兜底事件对场景韧性的增量


class Flywheel:
    def __init__(self, path: str = LEARNED_SIGNALS_PATH, runs_path: str = RUNS_PATH):
        self.path = path
        self.runs_path = runs_path

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

    # ---------- 历史留痕：reflect / history 读取 ----------
    def save_run(self, record: RunRecord) -> None:
        os.makedirs(os.path.dirname(self.runs_path), exist_ok=True)
        row = {
            "id": record.id,
            "ts": record.ts,
            "raw_goal": record.intent.raw_goal if record.intent else None,
            "chosen_plan_id": record.chosen_plan_id,
            "feedback": record.feedback,
            "replanned": record.replanned,
            "signals_emitted": record.signals_emitted,
            "fallback_triggered": record.fallback_triggered,
        }
        with open(self.runs_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def load_runs(self) -> List[dict]:
        if not os.path.exists(self.runs_path):
            return []
        out: List[dict] = []
        with open(self.runs_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

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

            # 场景级维度增量：把本次在该场景下表达的维度偏好沉淀到 scenario_overrides，
            # 供后续同场景会话以"场景优先"方式加权（区别于全局 user_pref_deltas）。
            for field in _DIMENSION_FIELDS:
                if getattr(intent, field, None) is not None:
                    over[field] = round(over.get(field, 0.0) + direction * _OVERRIDE_STEP, 3)
                    emitted.append(
                        f"scenario[{scenario_id}]:{field}{direction * _OVERRIDE_STEP:+.2f}")

            # 商家信号
            for slot in chosen_plan.slots:
                cur = signals.merchant_signals.get(slot.ref_id, 0.0)
                signals.merchant_signals[slot.ref_id] = round(cur + direction * _MERCHANT_STEP, 3)
                emitted.append(f"merchant:{slot.ref_id}{direction * _MERCHANT_STEP:+.2f}")

            # 兜底事件参与信号生成：
            # 1) 对被兜底淘汰的商家施加负向信号，下次降低其优先级；
            # 2) 在场景层累加"兜底韧性"增量，提示该场景需要更稳的候选。
            if fallback_triggered:
                for mid in getattr(chosen_plan, "rejected_merchants", []) or []:
                    cur = signals.merchant_signals.get(mid, 0.0)
                    signals.merchant_signals[mid] = round(cur - _MERCHANT_STEP, 3)
                    emitted.append(f"merchant:{mid}-{_MERCHANT_STEP:.2f}(fallback)")
                over = signals.scenario_overrides.setdefault(scenario_id, {})
                over["fallback_resilience"] = round(
                    over.get("fallback_resilience", 0.0) + _FALLBACK_STEP, 3)
                emitted.append(f"scenario[{scenario_id}]:fallback_resilience+{_FALLBACK_STEP:.2f}")

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
            self.save_run(record)
        return signals, record


def _scenario_emphasis(scenario_id: str) -> str:
    return {
        "family": "kid_balance",
        "friend": "group_lively",
        "date": "photogenic",
        "solo": "solo_pref",
    }.get(scenario_id, "vibe")
