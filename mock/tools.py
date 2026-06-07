"""Mock replacements for Meituan-style API surfaces.

Mapping and replacement path:
- mock_poi_query -> POI/search service; replace with merchant search API.
- mock_groupbuy -> deal/groupbuy detail service; replace with groupbuy goods API.
- mock_check_inventory -> SKU/stock service; replace with inventory API.
- mock_queue -> restaurant queue service; replace with dine-in queue/ticket API.
- mock_delivery -> instant delivery/scheduled gift service; replace with delivery order API.
- mock_mobility -> route planning service; replace with map mobility API.
- mock_reserve -> dining reservation service; replace with reservation API.
- mock_pay -> payment cashier service; replace with payment API.
- mock_geo_minutes -> route ETA service; replace with map ETA API.
- mock_weather -> local weather risk service; replace with weather API.

All real-ish behavior is kept inside MockClient. Module-level functions are
compatibility wrappers over the default client.
"""

import math
import random
import time
from datetime import datetime, timedelta


class MockClient:
    def __init__(self, latency_ms=(50, 200), failure_rates=None, seed=7):
        self.latency_ms = latency_ms
        self.failure_rates = failure_rates or {}
        self.random = random.Random(seed)

    def poi_query(self, keyword, zone=None, page_size=10):
        self._delay()
        pois = [
            self._poi("M101", "parent-child cafe", "cafe", zone or "People Square", "31.2304,121.4737", 4.7, 2),
            self._poi("M301", "bookstore activity", "activity", zone or "People Square", "31.2320,121.4750", 4.8, 2),
            self._poi("M102", "hotpot dinner", "restaurant", zone or "People Square", "31.2333,121.4771", 4.5, 3),
            self._poi("M218", "Cantonese claypot dinner", "restaurant", zone or "People Square", "31.2341,121.4760", 4.6, 3),
        ]
        keyword_lower = (keyword or "").lower()
        matched = [poi for poi in pois if keyword_lower in poi["name"].lower() or keyword_lower in poi["category"]]
        return (matched or pois)[:page_size]

    def groupbuy(self, merchant_id):
        self._delay()
        unavailable = self._failed("coupon_invalid") or merchant_id == "M118"
        price = 168 if merchant_id != "M218" else 186
        return {
            "groupbuy_id": f"GB{merchant_id[-3:]}",
            "merchant_id": merchant_id,
            "title": "family set coupon" if merchant_id != "M218" else "claypot dinner coupon",
            "original_price": price + 42,
            "price": price,
            "save": 42,
            "valid_until": "2026-06-30T23:59:59",
            "stock": 0 if unavailable else 12,
            "is_available": not unavailable,
            "status": "coupon_invalid" if unavailable else "available",
        }

    def check_inventory(self, item_id, qty=1):
        self._delay()
        sold_out = self._failed("sold_out") or item_id in {"M102", "sold_out"}
        available_qty = 0 if sold_out else max(qty, 6)
        return {
            "item_id": item_id,
            "requested_qty": qty,
            "available_qty": available_qty,
            "is_sufficient": available_qty >= qty,
            "next_available_time": "2026-06-08T11:00:00" if sold_out else None,
            "status": "sold_out" if sold_out else "available",
        }

    def queue(self, merchant_id):
        self._delay()
        full = self._failed("fully_booked")
        wait = 35 if merchant_id == "M102" else 8
        can_take = not full and wait >= 20
        return {
            "merchant_id": merchant_id,
            "queue_id": f"Q{merchant_id[-3:]}",
            "current_wait_minutes": wait if not full else 90,
            "position": 12 if can_take else None,
            "can_take_number": can_take,
            "number_taken": can_take,
            "status": "full" if full else "number_taken" if can_take else "no_wait",
        }

    def delivery(self, item_type, to_address, scheduled_time=None):
        self._delay()
        sold_out = self._failed("sold_out") and item_type in {"cake", "flower"}
        fee = 12 if item_type == "cake" else 9 if item_type == "flower" else 6
        eta_base = self._parse_time(scheduled_time) if scheduled_time else datetime(2026, 6, 7, 18, 20)
        return {
            "delivery_id": f"D{self.random.randint(1000, 9999)}",
            "item_type": item_type,
            "eta": eta_base.strftime("%Y-%m-%dT%H:%M:%S"),
            "fee": fee,
            "status": "sold_out" if sold_out else "scheduled" if scheduled_time else "created",
            "is_cancelable": not sold_out,
            "to_address": to_address,
        }

    def mobility(self, origin_geo, dest_geo, mode="walk"):
        self._delay()
        distance = self._distance_km(origin_geo, dest_geo)
        speed = {"walk": 4.5, "bike": 12, "taxi": 24}.get(mode, 4.5)
        minutes = max(5, int(distance / speed * 60) + (8 if mode == "taxi" else 0))
        return {
            "route_minutes": minutes,
            "distance_km": round(distance, 2),
            "mode": mode,
            "traffic_level": "medium" if mode == "taxi" else "low",
            "alternatives": [
                {"mode": "walk", "route_minutes": max(minutes, 12), "fee": 0},
                {"mode": "taxi", "route_minutes": max(8, minutes - 5), "fee": 18},
            ],
        }

    def reserve(self, merchant_id, slot_time, party_size=2):
        self._delay()
        full = self._failed("fully_booked") or merchant_id == "M102"
        return {
            "reservation_id": f"R{merchant_id[-3:]}",
            "merchant_id": merchant_id,
            "slot_time": slot_time,
            "party_size": party_size,
            "status": "full" if full else "reserved",
            "is_cancelable": not full,
            "cancel_deadline": "2026-06-07T16:40:00" if not full else None,
        }

    def pay(self, order_id, amount, method="meituan_pay"):
        self._delay()
        timeout = self._failed("timeout")
        return {
            "payment_id": f"P{self.random.randint(10000, 99999)}",
            "order_id": order_id,
            "amount": amount,
            "method": method,
            "status": "timeout" if timeout else "requires_confirmation",
            "paid_at": None,
            "is_refundable": not timeout,
        }

    def geo_minutes(self, origin_geo, dest_geo):
        self._delay()
        route = self.mobility(origin_geo, dest_geo, "walk")
        return {
            "origin_geo": origin_geo,
            "dest_geo": dest_geo,
            "route_minutes": route["route_minutes"],
            "distance_km": route["distance_km"],
        }

    def weather(self, zone, date, hour):
        self._delay()
        rainy = zone in {"People Square", "central"} or int(hour) >= 15
        return {
            "zone": zone,
            "date": date,
            "hour": hour,
            "condition": "rain" if rainy else "cloudy",
            "temperature": 24,
            "precipitation_prob": 0.72 if rainy else 0.24,
            "wind_level": 3,
            "outdoor_score": 42 if rainy else 78,
        }

    def _poi(self, poi_id, name, category, zone, geo_text, rating, price_level):
        lat, lng = _parse_geo(geo_text)
        closed = self._failed("closed") and category == "restaurant"
        return {
            "poi_id": poi_id,
            "name": name,
            "category": category,
            "address": f"{zone} mock street {poi_id[-2:]}",
            "zone": zone,
            "geo": {"lat": lat, "lng": lng},
            "rating": rating,
            "price_level": price_level,
            "tags": ["indoor", "refundable"] if category != "restaurant" else ["dinner", "queue_supported"],
            "open_hours": "10:00-22:00",
            "is_open": not closed,
        }

    def _delay(self):
        if not self.latency_ms:
            return
        if isinstance(self.latency_ms, (int, float)):
            delay_ms = float(self.latency_ms)
        else:
            delay_ms = self.random.randint(int(self.latency_ms[0]), int(self.latency_ms[1]))
        if delay_ms > 0:
            time.sleep(delay_ms / 1000)

    def _failed(self, key):
        return self.random.random() < float(self.failure_rates.get(key, 0))

    def _distance_km(self, origin_geo, dest_geo):
        lat1, lng1 = _parse_geo(origin_geo)
        lat2, lng2 = _parse_geo(dest_geo)
        return math.hypot((lat2 - lat1) * 111, (lng2 - lng1) * 95)

    def _parse_time(self, value):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%H:%M"):
            try:
                parsed = datetime.strptime(value, fmt)
                if fmt == "%H:%M":
                    return datetime(2026, 6, 7, parsed.hour, parsed.minute)
                return parsed
            except (TypeError, ValueError):
                pass
        return datetime(2026, 6, 7, 18, 20) + timedelta(minutes=30)


def _parse_geo(value):
    if isinstance(value, dict):
        return float(value["lat"]), float(value["lng"])
    lat, lng = str(value).split(",", 1)
    return float(lat), float(lng)


_DEFAULT_CLIENT = MockClient()


def configure_mock_client(client=None, **kwargs):
    global _DEFAULT_CLIENT
    _DEFAULT_CLIENT = client or MockClient(**kwargs)
    return _DEFAULT_CLIENT


def mock_poi_query(keyword, zone=None, page_size=10):
    return _DEFAULT_CLIENT.poi_query(keyword, zone, page_size)


def mock_groupbuy(merchant_id):
    return _DEFAULT_CLIENT.groupbuy(merchant_id)


def mock_check_inventory(item_id, qty=1):
    return _DEFAULT_CLIENT.check_inventory(item_id, qty)


def mock_queue(merchant_id):
    return _DEFAULT_CLIENT.queue(merchant_id)


def mock_delivery(item_type, to_address=None, scheduled_time=None):
    return _DEFAULT_CLIENT.delivery(item_type, to_address, scheduled_time)


def mock_mobility(origin_geo, dest_geo, mode="walk"):
    return _DEFAULT_CLIENT.mobility(origin_geo, dest_geo, mode)


def mock_reserve(merchant_id, slot_time, party_size=2):
    return _DEFAULT_CLIENT.reserve(merchant_id, slot_time, party_size)


def mock_pay(order_id, amount=None, method="meituan_pay"):
    if amount is None:
        amount = order_id
        order_id = "legacy_order"
    return _DEFAULT_CLIENT.pay(order_id, amount, method)


def mock_geo_minutes(origin_geo, dest_geo=None):
    if dest_geo is None and isinstance(origin_geo, list):
        slots = origin_geo
        total = 0
        for index in range(len(slots) - 1):
            total += _DEFAULT_CLIENT.geo_minutes(slots[index].geo, slots[index + 1].geo)["route_minutes"]
        return total
    return _DEFAULT_CLIENT.geo_minutes(origin_geo, dest_geo)


def mock_weather(zone="People Square", date="2026-06-07", hour=15):
    return _DEFAULT_CLIENT.weather(zone, date, hour)


def mock_flashbuy(item):
    delivery = _DEFAULT_CLIENT.delivery(item, "current route", None)
    return {"order_id": delivery["delivery_id"], "item": item, "eta_min": 22, "status": delivery["status"]}
