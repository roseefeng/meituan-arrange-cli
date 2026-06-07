import dataclasses
import time
from dataclasses import dataclass

from mock.tools import (
    mock_delivery,
    mock_flashbuy,
    mock_geo_minutes,
    mock_groupbuy,
    mock_mobility,
    mock_pay,
    mock_reserve,
)


@dataclass
class IntentFrame:
    raw_goal: str
    vibe: str
    setting: str
    effort: str
    spend: str
    meal_focus: str
    duration_hint: str
    sensitivities: list
    party: str
    fired_rules: list


@dataclass
class ScenarioTemplate:
    id: str
    label: str
    base_constraints: list
    weight_overrides: dict
    risk_extras: list


@dataclass
class Constraint:
    id: str
    kind: str
    reason: str


@dataclass
class PlanSlot:
    id: str
    name: str
    merchant_id: str
    geo: str
    window: str


@dataclass
class Plan:
    id: str
    title: str
    route_minutes: int
    slots: list
    constraints: list
    locked_items: list
    flexible_items: list
    score: float
    rejected_merchants: list


@dataclass
class PlannerOutput:
    intent: IntentFrame
    scenario_template: ScenarioTemplate
    plans: list
    chosen_plan: Plan
    candidate_count: int
    constraint_labels: list
    injected_signals: list

    def to_dict(self):
        return dataclasses.asdict(self)


@dataclass
class ToolCall:
    name: str
    status: str
    tool_input: dict
    tool_output: dict


@dataclass
class Execution:
    reversible_actions: list
    payment_confirmations: list
    tool_calls: list

    def to_dict(self):
        return dataclasses.asdict(self)


@dataclass
class Feedback:
    text: str
    source: str


@dataclass
class ReplanDiff:
    from_item: str
    to_item: str
    locked_items: list
    reason: str
    score_delta: float

    def to_dict(self):
        return dataclasses.asdict(self)


@dataclass
class LearnedSignals:
    user_pref_deltas: list
    merchant_signals: list
    scenario_overrides: dict
    last_updated: str

    def to_dict(self):
        return dataclasses.asdict(self)


@dataclass
class SessionState:
    profile: dict
    runs: list


@dataclass
class RunRecord:
    id: str
    ts: str
    intent: dict
    chosen_plan_id: str
    feedback: dict
    replanned: bool
    signals_emitted: bool
    fallback_triggered: bool


class Planner:
    def plan(self, raw_goal, scenario):
        template = ScenarioTemplate(
            id=scenario,
            label={"family": "family outing", "friend": "friends meetup", "date": "date plan", "solo": "solo reset"}[
                scenario
            ],
            base_constraints=["short transfer", "payment confirmation", "weather backup"],
            weight_overrides={"risk": 1.3, "distance": 1.2, "price": 0.9},
            risk_extras=["rain", "crowding"],
        )
        intent = IntentFrame(
            raw_goal=raw_goal,
            vibe="easy and predictable",
            setting="nearby indoor-first route",
            effort="low",
            spend="moderate",
            meal_focus="not too spicy",
            duration_hint="half day",
            sensitivities=["rain", "crowding"],
            party="one adult and one child" if scenario == "family" else "one person" if scenario == "solo" else "two people",
            fired_rules=["prefer_refundable", "cap_route_minutes", "keep_backup"],
        )
        plans = self._plans(scenario)
        return PlannerOutput(
            intent=intent,
            scenario_template=template,
            plans=plans,
            chosen_plan=plans[0],
            candidate_count=8,
            constraint_labels=template.base_constraints,
            injected_signals=["repo:weather=rain", "repo:merchant:M102 crowd risk"],
        )

    def _plans(self, scenario):
        first_slot = "parent-child cafe" if scenario == "family" else "quiet cafe"
        constraints = [
            Constraint("c_route", "route", "route stays under 60 minutes"),
            Constraint("c_pay", "payment", "new paid deltas need confirmation"),
            Constraint("c_weather", "weather", "indoor backup is available under rain"),
        ]
        return [
            Plan(
                id="plan_A",
                title="low-risk route with indoor backup",
                route_minutes=42,
                slots=[
                    PlanSlot("slot_1", first_slot, "M101", "31.2304,121.4737", "15:00-16:10"),
                    PlanSlot("slot_2", "bookstore activity", "M301", "31.2320,121.4750", "16:20-17:20"),
                    PlanSlot("slot_3", "hotpot dinner", "M102", "31.2333,121.4771", "17:40-19:00"),
                ],
                constraints=constraints,
                locked_items=["start time", "bookstore activity"],
                flexible_items=["dinner merchant", "delivery dessert"],
                score=0.87,
                rejected_merchants=["M201 too crowded", "M305 no refund window"],
            ),
            Plan(
                id="plan_B",
                title="cheaper route with longer transfer",
                route_minutes=58,
                slots=[
                    PlanSlot("slot_1", "mall activity", "M401", "31.2250,121.4800", "15:00-16:30"),
                    PlanSlot("slot_2", "noodle dinner", "M402", "31.2280,121.4820", "17:00-18:00"),
                ],
                constraints=constraints,
                locked_items=["budget cap"],
                flexible_items=["activity merchant", "ride mode"],
                score=0.78,
                rejected_merchants=["M118 expired coupon"],
            ),
        ]


class Replanner:
    def replan_for_fallback(self, plan, fallback_event):
        target_name, target_merchant_id = _parse_fallback_target(fallback_event.to_item)
        slots = [
            dataclasses.replace(slot, name=target_name, merchant_id=target_merchant_id)
            if slot.id == fallback_event.affected_slot_id
            else slot
            for slot in plan.slots
        ]
        return dataclasses.replace(
            plan,
            id=f"{plan.id}_fallback",
            title=f"low-risk route with {target_name} fallback",
            slots=slots,
            flexible_items=["delivery dessert"],
        )

    def replan_for_feedback(self, plan, feedback):
        if feedback.source == "self_state":
            return ReplanDiff(
                "bookstore activity plus dinner",
                "tea room plus nearby noodle dinner",
                ["start time", "weather-safe indoor anchor"],
                "self state changed, so walking and noise are reduced",
                0.04,
            )
        return ReplanDiff(
            "hotpot dinner",
            "Cantonese claypot dinner",
            ["start time", "bookstore activity", "route direction"],
            "companion preference lowers spice risk while preserving route",
            0.06,
        )

    def replan_plan_for_feedback(self, plan, feedback):
        diff = self.replan_for_feedback(plan, feedback)
        slots = list(plan.slots)
        if feedback.source == "self_state":
            slots = [
                dataclasses.replace(slot, name="tea room", merchant_id="M501")
                if index == 1
                else dataclasses.replace(slot, name="nearby noodle dinner", merchant_id="M502")
                if index == len(plan.slots) - 1
                else slot
                for index, slot in enumerate(plan.slots)
            ]
        else:
            slots = [
                dataclasses.replace(slot, name=diff.to_item, merchant_id="M218")
                if index == len(plan.slots) - 1
                else slot
                for index, slot in enumerate(plan.slots)
            ]
        return dataclasses.replace(
            plan,
            id=f"{plan.id}_feedback",
            title=f"{plan.title} adjusted by feedback",
            slots=slots,
            locked_items=list(diff.locked_items),
            flexible_items=["feedback-adjusted meal", "arrival buffer"],
        )


class Executor:
    def execute(self, plan):
        dinner = plan.slots[-1]
        groupbuy = mock_groupbuy(dinner.merchant_id)
        tool_calls = [
            ToolCall("mock_geo_minutes", "done", {"plan_id": plan.id}, {"minutes": mock_geo_minutes(plan.slots)}),
            ToolCall(
                "mock_reserve",
                "done",
                {"merchant_id": dinner.merchant_id, "slot_time": dinner.window, "party_size": 2},
                mock_reserve(dinner.merchant_id, dinner.window, 2),
            ),
            ToolCall("mock_groupbuy", "pending-confirm", {"merchant_id": dinner.merchant_id}, groupbuy),
            ToolCall(
                "mock_delivery",
                "done",
                {"item_type": "dessert", "to_address": dinner.geo, "scheduled_time": None},
                mock_delivery("dessert", dinner.geo),
            ),
            ToolCall(
                "mock_mobility",
                "done",
                {"origin_geo": plan.slots[0].geo, "dest_geo": plan.slots[1].geo, "mode": "walk"},
                mock_mobility(plan.slots[0].geo, plan.slots[1].geo, "walk"),
            ),
            ToolCall("mock_flashbuy", "done", {"item": "rain poncho"}, mock_flashbuy("rain poncho")),
            ToolCall(
                "mock_pay",
                "needs-confirm",
                {"order_id": groupbuy["groupbuy_id"], "amount": groupbuy["price"], "method": "meituan_pay"},
                mock_pay(groupbuy["groupbuy_id"], groupbuy["price"], "meituan_pay"),
            ),
        ]
        return Execution(
            reversible_actions=[f"reserve {dinner.name}", "hold bookstore seat"],
            payment_confirmations=[f"groupbuy {groupbuy['title']} {groupbuy['price']} y/n"],
            tool_calls=tool_calls,
        )

    def feedback_for(self, scenario, feedback_text=None):
        if feedback_text:
            return Feedback(feedback_text, "self_state" if scenario == "solo" else "user")
        if scenario == "solo":
            return Feedback("I feel tired; reduce walking and keep dinner nearby.", "self_state")
        return Feedback("Grandparent prefers less spicy dinner.", "companion")

    def emit_signals(self, feedback, fallback_event):
        merchant_signals = []
        if fallback_event:
            merchant_signals.append(f"{fallback_event.from_item} unavailable: {fallback_event.reason}")
        return LearnedSignals(
            user_pref_deltas=[f"{feedback.source}: {feedback.text}"],
            merchant_signals=merchant_signals or ["no merchant change"],
            scenario_overrides={"prefer_refundable": True, "avoid_crowded_dinner": bool(fallback_event)},
            last_updated=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )

    def build_run_record(self, planning, chosen_plan, feedback, replanned, signals, fallback_triggered):
        ts = _run_ts()
        return RunRecord(
            id=f"run_{ts}",
            ts=ts,
            intent=dataclasses.asdict(planning.intent),
            chosen_plan_id=chosen_plan.id,
            feedback=dataclasses.asdict(feedback),
            replanned=replanned,
            signals_emitted=bool(signals.user_pref_deltas or signals.merchant_signals),
            fallback_triggered=fallback_triggered,
        )


def plan_from_dict(payload):
    constraints = [Constraint(**item) for item in payload["constraints"]]
    slots = [PlanSlot(**item) for item in payload["slots"]]
    return Plan(
        id=payload["id"],
        title=payload["title"],
        route_minutes=payload["route_minutes"],
        slots=slots,
        constraints=constraints,
        locked_items=payload["locked_items"],
        flexible_items=payload["flexible_items"],
        score=payload["score"],
        rejected_merchants=payload["rejected_merchants"],
    )


def planner_output_from_dict(payload):
    plans = [plan_from_dict(item) for item in payload["plans"]]
    chosen = plan_from_dict(payload["chosen_plan"])
    return PlannerOutput(
        intent=IntentFrame(**payload["intent"]),
        scenario_template=ScenarioTemplate(**payload["scenario_template"]),
        plans=plans,
        chosen_plan=chosen,
        candidate_count=payload["candidate_count"],
        constraint_labels=payload["constraint_labels"],
        injected_signals=payload["injected_signals"],
    )


def _run_ts():
    base = time.strftime("%Y%m%d%H%M%S")
    millis = int((time.time() % 1) * 1000)
    return f"{base}{millis:03d}"


def _parse_fallback_target(value):
    if " at " not in value:
        return value, "M218"
    name, merchant_id = value.rsplit(" at ", 1)
    return name, merchant_id
