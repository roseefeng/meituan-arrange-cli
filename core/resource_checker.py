import dataclasses
from dataclasses import dataclass

try:
    from mock import repository
except ImportError:
    repository = None

from mock.tools import MockClient, mock_check_inventory, mock_delivery, mock_groupbuy, mock_mobility, mock_queue, mock_reserve, mock_weather


@dataclass
class FallbackEvent:
    id: str
    reason: str
    affected_slot_id: str
    from_item: str
    to_item: str
    locked_items: list
    money_delta: float
    checks: list


@dataclass
class ResourceResult:
    fallback_event: FallbackEvent
    checks: list
    reversible_actions: list
    payment_confirmations: list
    slot_window_updates: list

    def to_dict(self):
        return dataclasses.asdict(self)


class ResourceChecker:
    def __init__(self, client=None):
        self.client = client

    def check_plan(self, plan):
        dinner = plan.slots[-1]
        merchant = self._merchant(dinner.merchant_id)
        client = self.client
        groupbuy = client.groupbuy(dinner.merchant_id) if client else mock_groupbuy(dinner.merchant_id)
        inventory = (
            client.check_inventory(dinner.merchant_id, 1)
            if client
            else mock_check_inventory(dinner.merchant_id, 1)
        )
        reservation = client.reserve(dinner.merchant_id, dinner.window, 2) if client else mock_reserve(dinner.merchant_id, dinner.window, 2)
        queue = client.queue(dinner.merchant_id) if client else mock_queue(dinner.merchant_id)
        surprise = self._surprise_delivery(plan, dinner)
        route = client.mobility(plan.slots[0].geo, plan.slots[1].geo, "walk") if client else mock_mobility(plan.slots[0].geo, plan.slots[1].geo, "walk")
        weather = client.weather("People Square", "2026-06-07", 15) if client else mock_weather("People Square", "2026-06-07", 15)
        reversible_actions = []
        payment_confirmations = []
        slot_window_updates = []
        if queue["can_take_number"]:
            reversible_actions.append(
                f"queue ticket {queue['queue_id']} position {queue['position']} wait {queue['current_wait_minutes']}min"
            )
            if len(plan.slots) >= 2:
                slot_window_updates.append(
                    {
                        "slot_id": plan.slots[-2].id,
                        "window": f"use {queue['current_wait_minutes']}min queue window for nearby activity",
                    }
                )
        if surprise and surprise["status"] not in {"sold_out", "timeout"}:
            reversible_actions.append(f"cancel surprise delivery {surprise['delivery_id']}")
            payment_confirmations.append(f"surprise delivery {surprise['item_type']} fee {surprise['fee']} y/n")
        checks = [
            f"open_hours={'pass' if merchant['open'] else 'fail'}",
            f"inventory={'pass' if merchant['inventory'] and inventory['is_sufficient'] else 'fail'}",
            f"crowd={'fail' if merchant['crowded'] else 'pass'}",
            f"reserve={'pass' if reservation['status'] == 'reserved' else 'fail'}",
            f"groupbuy={'pass' if groupbuy['is_available'] else 'fail'}",
            f"queue={queue['status']}",
            f"route={route['route_minutes']}min",
            f"weather={weather['condition']}",
        ]
        unavailable = (
            not merchant["open"]
            or not merchant["inventory"]
            or not inventory["is_sufficient"]
            or merchant["crowded"]
            or not groupbuy["is_available"]
            or reservation["status"] != "reserved"
        )
        if unavailable:
            to_item = "nearby noodle dinner at M502" if dinner.merchant_id == "M218" else "Cantonese claypot dinner at M218"
            return ResourceResult(
                fallback_event=FallbackEvent(
                    id="fallback_001",
                    reason=f"{dinner.merchant_id} key resource unavailable during real repository check",
                    affected_slot_id=dinner.id,
                    from_item=f"{dinner.name} at {dinner.merchant_id}",
                    to_item=to_item,
                    locked_items=[plan.slots[0].name, plan.slots[1].name, "route direction"],
                    money_delta=18,
                    checks=checks,
                ),
                checks=checks,
                reversible_actions=reversible_actions,
                payment_confirmations=payment_confirmations,
                slot_window_updates=slot_window_updates,
            )
        return ResourceResult(
            fallback_event=None,
            checks=checks,
            reversible_actions=reversible_actions,
            payment_confirmations=payment_confirmations,
            slot_window_updates=slot_window_updates,
        )

    def confirm_execution(self, execution):
        return {"status": "confirmed", "tool_calls": len(execution.tool_calls)}

    def _merchant(self, merchant_id):
        if repository and hasattr(repository, "get_merchant"):
            merchant = repository.get_merchant(merchant_id)
            return {
                "open": bool(getattr(merchant, "open", merchant.get("open", True))),
                "inventory": bool(getattr(merchant, "inventory", merchant.get("inventory", True))),
                "crowded": bool(getattr(merchant, "crowded", merchant.get("crowded", False))),
            }
        return {"open": True, "inventory": True, "crowded": merchant_id == "M102"}

    def _surprise_delivery(self, plan, dinner):
        item_type = None
        for item in plan.flexible_items:
            lowered = item.lower()
            if "cake" in lowered:
                item_type = "cake"
            elif "flower" in lowered:
                item_type = "flower"
            elif "delivery" in lowered or "dessert" in lowered:
                item_type = "cake"
            if item_type:
                break
        if not item_type:
            return None
        if self.client:
            return self.client.delivery(item_type, dinner.geo, "2026-06-07T18:30:00")
        return mock_delivery(item_type, dinner.geo, "2026-06-07T18:30:00")
