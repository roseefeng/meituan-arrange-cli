"""关键词规则表：六维语义 + party 解析。

每条规则 = (name, dimension, value, keywords)。parser 扫描 raw_goal，
命中即设维度值并记录 (name, span)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# 单值维度
VIBE = "vibe"
SETTING = "setting"
EFFORT = "effort"
SPEND = "spend"
MEAL_FOCUS = "meal_focus"
DURATION = "duration_hint"
# 多值维度
SENSITIVITY = "sensitivities"


@dataclass(frozen=True)
class Rule:
    name: str
    dimension: str
    value: str
    keywords: tuple


# ----- 六维规则表 -----
DIMENSION_RULES: List[Rule] = [
    # vibe：松弛 / 热闹 / 文艺 / 出片
    Rule("vibe-松弛", VIBE, "松弛", ("随便逛逛", "松弛", "放松", "随便走走", "歇歇")),
    Rule("vibe-热闹", VIBE, "热闹", ("嗨", "热闹", "玩起来", "蹦", "嗨皮", "热闹点")),
    Rule("vibe-文艺", VIBE, "文艺", ("文艺", "安静", "展", "书店", "小众")),
    Rule("vibe-出片", VIBE, "出片", ("拍照", "出片", "打卡", "美美", "好看")),

    # setting：室内 / 室外 / 商场 / 公园
    Rule("setting-室外", SETTING, "室外", ("晒太阳", "透气", "走走", "户外", "外面")),
    Rule("setting-室内", SETTING, "室内", ("下雨", "商场", "室内", "怕晒", "空调")),
    Rule("setting-公园", SETTING, "公园", ("公园", "绿地", "草地")),
    Rule("setting-商场", SETTING, "商场", ("逛商场", "购物中心", "mall")),

    # effort：躺平 / 轻度 / 能折腾
    Rule("effort-躺平", EFFORT, "躺平", ("不想动", "就近", "躺平", "懒", "原地")),
    Rule("effort-能折腾", EFFORT, "能折腾", ("随便走多远都行", "能折腾", "折腾", "走多远都行", "跑远点")),
    Rule("effort-轻度", EFFORT, "轻度", ("走走", "轻松点", "溜达")),

    # spend：省 / 适中 / 不在乎
    Rule("spend-省", SPEND, "省", ("经济", "划算", "省点", "便宜", "穷")),
    Rule("spend-不在乎", SPEND, "不在乎", ("好一点", "犒劳", "犒劳一下", "不差钱", "贵点没关系")),
    Rule("spend-适中", SPEND, "适中", ("适中", "正常", "一般般")),

    # meal_focus：正餐 / 小吃 / 咖啡 / 不重要
    Rule("meal-正餐", MEAL_FOCUS, "正餐", ("吃顿好的", "正餐", "好好吃", "吃大餐", "搓一顿")),
    Rule("meal-小吃", MEAL_FOCUS, "小吃", ("随便垫垫", "小吃", "垫垫", "简单吃", "随便吃点")),
    Rule("meal-咖啡", MEAL_FOCUS, "咖啡", ("找地方坐坐", "坐坐", "咖啡", "喝杯", "下午茶")),
    Rule("meal-不重要", MEAL_FOCUS, "不重要", ("吃不吃无所谓", "不用吃", "吃过了")),

    # duration_hint：短 / 半天 / 全天
    Rule("dur-短", DURATION, "短", ("一会儿", "俩小时", "两小时", "快去快回")),
    Rule("dur-半天", DURATION, "半天", ("半天", "下午", "上午")),
    Rule("dur-全天", DURATION, "全天", ("一整天", "全天", "玩一天")),

    # sensitivities（多值）
    Rule("sens-减脂", SENSITIVITY, "减脂", ("减脂", "减肥", "低卡", "健康点")),
    Rule("sens-忌辣", SENSITIVITY, "忌辣", ("忌辣", "不能吃辣", "不吃辣", "怕辣")),
    Rule("sens-孩子友好", SENSITIVITY, "孩子友好", ("带孩子", "孩子", "娃", "宝宝", "小孩")),
    Rule("sens-低强度", SENSITIVITY, "低强度", ("老人", "走不动", "不能久走", "腿脚", "长辈")),
]


# ----- party 解析规则 -----
# scenario_hint 优先级：family > date > friend > solo
@dataclass(frozen=True)
class PartyRule:
    name: str
    role: str            # 写入 IntentFrame.party
    scenario_hint: str   # family / friend / date / solo
    keywords: tuple


PARTY_RULES: List[PartyRule] = [
    PartyRule("party-solo", "user", "solo", ("自己", "一个人", "独自", "我自己", "单人")),
    PartyRule("party-kid", "kid", "family", ("孩子", "娃", "宝宝", "小孩")),
    PartyRule("party-elder", "elder", "family", ("老人", "父母", "爸妈", "长辈")),
    PartyRule("party-family", "family", "family", ("老婆", "老公", "媳妇", "家人", "全家")),
    PartyRule("party-date", "partner", "date", ("对象", "约会", "男朋友", "女朋友", "男友", "女友")),
    PartyRule("party-friend", "friends", "friend", ("朋友", "哥们", "姐妹", "一帮人", "几个人", "同事")),
]

SCENARIO_PRIORITY = {"family": 3, "date": 2, "friend": 1, "solo": 0}


def find_first_span(text: str, keywords: tuple) -> Optional[tuple]:
    """返回最早命中的关键词 span (start, end)，无命中返回 None。"""
    best: Optional[tuple] = None
    for kw in keywords:
        idx = text.find(kw)
        if idx != -1:
            span = (idx, idx + len(kw))
            if best is None or span[0] < best[0]:
                best = span
    return best
