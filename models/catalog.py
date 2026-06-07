from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Activity:
    """活动候选。geo 为新增字段（来源 = 本次增补）。"""

    id: str
    name: str
    geo: str                      # zone 字符串（新增字段）
    vibe: str                     # 松弛 / 热闹 / 文艺 / 出片
    setting: str                  # 室内 / 室外 / 商场 / 公园
    effort: str                   # 躺平 / 轻度 / 能折腾
    spend: str                    # 省 / 适中 / 不在乎
    duration_min: int = 90
    tags: List[str] = field(default_factory=list)
    kid_friendly: bool = False
    low_intensity: bool = False
    solo_friendly: bool = False
    photogenic: bool = False
    scenarios: List[str] = field(default_factory=list)   # 适配场景提示


@dataclass
class Restaurant:
    """餐饮候选。geo 为新增字段（来源 = 本次增补）。"""

    id: str
    name: str
    geo: str                      # zone 字符串（新增字段）
    meal_focus: str               # 正餐 / 小吃 / 咖啡
    spend: str                    # 省 / 适中 / 不在乎
    vibe: str = "松弛"
    duration_min: int = 60
    tags: List[str] = field(default_factory=list)
    low_cal: bool = False
    spicy: bool = False
    kid_friendly: bool = False
    solo_friendly: bool = False
    photogenic: bool = False
    scenarios: List[str] = field(default_factory=list)


@dataclass
class GroupBuy:
    """团购券（新增数据集）。"""

    id: str
    merchant_id: str
    title: str
    price: float
    save: float
