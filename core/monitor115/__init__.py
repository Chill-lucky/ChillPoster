"""
core.monitor115 — 115 生活事件监控模块

提供 115 网盘生活事件的轮询监控能力，支持目录过滤和事件回调。

使用方式:
    from core.monitor115 import LifeEventMonitor

    monitor = LifeEventMonitor(
        client=p115_client,
        source_dir="/转存测试",
        target_dir="/媒体库",
        callback=lambda path, fid, name: print(f"事件: {name} -> {path}"),
    )
    monitor.start()
    # ... 运行中 ...
    monitor.stop()
"""
from .monitor import LifeEventMonitor, create_monitor, life_event_monitor
from .models import LifeEvent, BEHAVIOR_TYPE_TO_NAME, INTERESTING_EVENT_TYPES, EVENT_TYPE_TO_CHINESE

__all__ = [
    "LifeEventMonitor",
    "create_monitor",
    "life_event_monitor",
    "LifeEvent",
    "BEHAVIOR_TYPE_TO_NAME",
    "INTERESTING_EVENT_TYPES",
    "EVENT_TYPE_TO_CHINESE",
]
