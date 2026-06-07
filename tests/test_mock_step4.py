import dataclasses
import re
import unittest

from cli.render import render_share
from core.executor import Planner, Replanner
from core.resource_checker import ResourceChecker
from mock.tools import MockClient, mock_queue


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text):
    return ANSI_RE.sub("", text)


class MockStep4Test(unittest.TestCase):
    def test_mock_io_shapes(self):
        client = MockClient(latency_ms=0)
        poi = client.poi_query("dinner", "People Square", 1)[0]
        self.assertEqual(
            set(poi),
            {"poi_id", "name", "category", "address", "zone", "geo", "rating", "price_level", "tags", "open_hours", "is_open"},
        )
        self.assertEqual(
            set(client.groupbuy("M218")),
            {"groupbuy_id", "merchant_id", "title", "original_price", "price", "save", "valid_until", "stock", "is_available", "status"},
        )
        self.assertEqual(
            set(client.check_inventory("M218", 2)),
            {"item_id", "requested_qty", "available_qty", "is_sufficient", "next_available_time", "status"},
        )
        self.assertEqual(
            set(client.queue("M102")),
            {"merchant_id", "queue_id", "current_wait_minutes", "position", "can_take_number", "number_taken", "status"},
        )
        self.assertEqual(
            set(client.delivery("cake", "31.23,121.47", "2026-06-07T18:30:00")),
            {"delivery_id", "item_type", "eta", "fee", "status", "is_cancelable", "to_address"},
        )
        self.assertEqual(
            set(client.mobility("31.2304,121.4737", "31.2320,121.4750", "walk")),
            {"route_minutes", "distance_km", "mode", "traffic_level", "alternatives"},
        )
        self.assertEqual(
            set(client.reserve("M218", "17:40-19:00", 2)),
            {"reservation_id", "merchant_id", "slot_time", "party_size", "status", "is_cancelable", "cancel_deadline"},
        )
        self.assertEqual(
            set(client.pay("O1", 12, "meituan_pay")),
            {"payment_id", "order_id", "amount", "method", "status", "paid_at", "is_refundable"},
        )
        self.assertEqual(
            set(client.geo_minutes("31.2304,121.4737", "31.2320,121.4750")),
            {"origin_geo", "dest_geo", "route_minutes", "distance_km"},
        )
        self.assertEqual(
            set(client.weather("People Square", "2026-06-07", 15)),
            {"zone", "date", "hour", "condition", "temperature", "precipitation_prob", "wind_level", "outdoor_score"},
        )

    def test_failure_injection_triggers_fallback(self):
        plan = Planner().plan("family route", "family").chosen_plan
        open_plan = dataclasses.replace(
            plan,
            slots=[dataclasses.replace(slot, merchant_id="M218", name="Cantonese claypot dinner") if slot.id == "slot_3" else slot for slot in plan.slots],
        )
        result = ResourceChecker(MockClient(latency_ms=0, failure_rates={"fully_booked": 1})).check_plan(open_plan)
        self.assertIsNotNone(result.fallback_event)
        self.assertIn("M218", result.fallback_event.reason)
        replanned = Replanner().replan_for_fallback(open_plan, result.fallback_event)
        self.assertEqual(replanned.slots[-1].merchant_id, "M502")

    def test_render_share_uses_first_slot(self):
        plan = Planner().plan("family route", "family").chosen_plan
        share = strip_ansi(render_share(plan))
        self.assertIn("15:00出发", share)
        self.assertIn("先去亲子咖啡馆", share)
        self.assertIn("预计19:00结束", share)

    def test_mock_queue_can_take_number(self):
        queue = mock_queue("M102")
        self.assertEqual(queue["merchant_id"], "M102")
        self.assertTrue(queue["can_take_number"])
        self.assertTrue(queue["number_taken"])


if __name__ == "__main__":
    unittest.main()
