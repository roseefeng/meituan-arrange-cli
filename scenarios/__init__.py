"""四场景对外封装。模板定义的单一真源在 core.scenario_templates，
此处仅做面向调用方的命名空间聚合。"""

from . import family, friend, date, solo

__all__ = ["family", "friend", "date", "solo"]
