# Step 4 E2E Scripts

Run with the same Python interpreter used for tests:

```bash
python scripts/e2e_all_scenarios.py
python scripts/two_session_flywheel.py
```

Both scripts isolate session, run transcript, and learned-signal files through environment variables:

- `MEITUAN_SESSION_PATH`
- `MEITUAN_RUNS_DIR`
- `MEITUAN_LEARNED_PATH`

`e2e_all_scenarios.py` executes family, friend, date, and solo flows and checks user/verbose output boundaries.

`two_session_flywheel.py` verifies that a first session emits `data/learned`-compatible LearnedSignals and a second similar plan injects history, producing a changed Plan A summary.

## Mock to real API mapping

`mock/tools.py` keeps all API-shaped behavior inside `MockClient`; module-level `mock_*` functions are compatibility wrappers. Replace them as follows when wiring real services:

- `mock_poi_query(keyword, zone, page_size)` -> POI/search API.
- `mock_groupbuy(merchant_id)` -> groupbuy/deal detail API.
- `mock_check_inventory(item_id, qty)` -> SKU inventory API.
- `mock_queue(merchant_id)` -> restaurant queue/ticket API.
- `mock_delivery(item_type, to_address, scheduled_time)` -> instant delivery or scheduled gift API.
- `mock_mobility(origin_geo, dest_geo, mode)` and `mock_geo_minutes(origin_geo, dest_geo)` -> map route/ETA API.
- `mock_reserve(merchant_id, slot_time, party_size)` -> dining reservation API.
- `mock_pay(order_id, amount, method)` -> cashier/payment API.
- `mock_weather(zone, date, hour)` -> local weather API.
