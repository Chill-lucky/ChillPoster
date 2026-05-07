"""
115 生活事件数据模型和事件类型常量

复刻自 p115strmhelper 插件的事件定义，脱离 MoviePilot 框架独立运行。
"""
from dataclasses import dataclass, field
from typing import FrozenSet

from p115client.tool.life import (
    BEHAVIOR_TYPE_TO_NAME,
    BEHAVIOR_NAME_TO_TYPE,
    IGNORE_BEHAVIOR_TYPES,
)

# 重新导出，方便外部模块使用
__all__ = [
    "LifeEvent",
    "BEHAVIOR_TYPE_TO_NAME",
    "BEHAVIOR_NAME_TO_TYPE",
    "IGNORE_BEHAVIOR_TYPES",
    "INTERESTING_EVENT_TYPES",
    "EVENT_TYPE_TO_CHINESE",
]

# 我们关心的事件类型（过滤掉浏览、收藏等无意义事件）
# 1=上传图片, 2=上传文件, 5=移动图片, 6=移动文件,
# 14=接收文件, 17=新建文件夹, 18=复制文件夹, 20=文件夹重命名, 22=删除文件
INTERESTING_EVENT_TYPES: FrozenSet[int] = frozenset(
    set(BEHAVIOR_NAME_TO_TYPE.values()) - IGNORE_BEHAVIOR_TYPES
)

# 事件类型中文映射
EVENT_TYPE_TO_CHINESE: dict[int, str] = {
    1: "新增图片",
    2: "新增文件",
    3: "标星图片",
    4: "标星文件/目录",
    5: "移动图片",
    6: "移动文件/目录",
    7: "浏览图片",
    8: "浏览视频",
    9: "浏览音频",
    10: "浏览文档",
    14: "接收文件",
    17: "新建文件夹",
    18: "复制文件夹",
    19: "文件夹标签",
    20: "文件夹重命名",
    22: "删除文件/目录",
    23: "复制文件",
    24: "文件重命名",
}


@dataclass
class LifeEvent:
    """115 生活事件数据类

    从 115 API 返回的原始事件字典中提取关键字段，同时保留原始数据用于调试。
    """
    event_id: str = ""          # 事件 ID
    event_type: int = 0         # 事件类型编号（1, 2, 5, 6, ...）
    event_name: str = ""        # 事件类型名称（"upload_file", "move_file", ...）
    file_id: str = ""           # 文件/目录 ID
    file_name: str = ""         # 文件/目录名称
    file_path: str = ""         # 文件完整路径（经过解析后填充）
    file_cid: str = ""          # 父目录 ID
    update_time: int = 0        # 事件时间戳
    event_type_cn: str = ""     # 事件类型中文名（如 "新增文件"、"移动文件"）
    raw: dict = field(default_factory=dict)  # 原始事件字典

    @classmethod
    def from_raw(cls, raw: dict, resolved_path: str = "") -> "LifeEvent":
        """从 115 API 返回的原始事件字典构建 LifeEvent

        Args:
            raw: 115 API 返回的事件字典
            resolved_path: 已解析的完整文件路径（可选）

        Returns:
            LifeEvent 实例
        """
        event_type = int(raw.get("type", 0))
        return cls(
            event_id=str(raw.get("id", "")),
            event_type=event_type,
            event_name=raw.get("event_name", BEHAVIOR_TYPE_TO_NAME.get(event_type, "")),
            event_type_cn=EVENT_TYPE_TO_CHINESE.get(event_type, f"未知({event_type})"),
            file_id=str(raw.get("file_id", "")),
            file_name=raw.get("file_name", ""),
            file_path=resolved_path or raw.get("file_path", ""),
            file_cid=str(raw.get("cid", raw.get("parent_id", ""))),
            update_time=int(raw.get("update_time", 0)),
            raw=raw,
        )
