"""本地 mock 数据访问层 + 动线近似。

mock_geo_minutes 在 Step 1 用 repository 内可读的 zone 坐标做本地近似，
后续可由 Codex 侧真实地理服务替换，签名保持不变。
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from models import Activity, Restaurant, GroupBuy

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# zone 坐标（网格），mock_geo_minutes 据此近似跨区通勤时间。
_ZONE_COORDS: Dict[str, tuple] = {
    "central": (0, 0),
    "riverside": (1, 0),
    "oldtown": (0, 1),
    "techpark": (2, 1),
    "lakeside": (1, 2),
    "uptown": (2, 2),
}

_SAME_ZONE_MINUTES = 5
_PER_HOP_MINUTES = 12     # 每一格曼哈顿距离的通勤分钟
_BASE_MINUTES = 4        # 跨区基础开销


def _load_json(name: str) -> list:
    with open(os.path.join(_DATA_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


class Repository:
    def __init__(self) -> None:
        self.activities: List[Activity] = [Activity(**d) for d in _load_json("activities.json")]
        self.restaurants: List[Restaurant] = [Restaurant(**d) for d in _load_json("restaurants.json")]
        self.groupbuys: List[GroupBuy] = [GroupBuy(**d) for d in _load_json("groupbuys.json")]
        self._gb_by_merchant: Dict[str, GroupBuy] = {g.merchant_id: g for g in self.groupbuys}

    # ----- 候选查询 -----
    def activities_for(self, scenario_id: str) -> List[Activity]:
        return [a for a in self.activities if scenario_id in a.scenarios]

    def restaurants_for(self, scenario_id: str) -> List[Restaurant]:
        return [r for r in self.restaurants if scenario_id in r.scenarios]

    def groupbuy_for(self, merchant_id: str) -> Optional[GroupBuy]:
        return self._gb_by_merchant.get(merchant_id)

    # ----- 动线近似 -----
    def mock_geo_minutes(self, geo_a: str, geo_b: str) -> int:
        if geo_a == geo_b:
            return _SAME_ZONE_MINUTES
        ca = _ZONE_COORDS.get(geo_a)
        cb = _ZONE_COORDS.get(geo_b)
        if ca is None or cb is None:
            return 30  # 未知 zone 的保守估计
        manhattan = abs(ca[0] - cb[0]) + abs(ca[1] - cb[1])
        return _BASE_MINUTES + manhattan * _PER_HOP_MINUTES


_REPO_SINGLETON: Optional[Repository] = None


def get_repository() -> Repository:
    global _REPO_SINGLETON
    if _REPO_SINGLETON is None:
        _REPO_SINGLETON = Repository()
    return _REPO_SINGLETON


def mock_geo_minutes(geo_a: str, geo_b: str) -> int:
    """模块级便捷入口，与 Codex 约定的签名一致。"""
    return get_repository().mock_geo_minutes(geo_a, geo_b)


# LearnedSignals 持久化路径（flywheel 使用）
LEARNED_SIGNALS_PATH = os.path.join(_DATA_DIR, "learned_signals.json")
# RunRecord 历史留痕路径（reflect / history 命令读取，JSON Lines 追加）
RUNS_PATH = os.path.join(_DATA_DIR, "runs.jsonl")
