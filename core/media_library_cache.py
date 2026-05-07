import json
import os
import threading
import time

from core.configs import MEDIA_LIBRARY_CACHE_FILE

_lock = threading.Lock()

# pickcode 索引：lazy invalidation，mutation 时标记 dirty，读取时按需重建
_pickcode_index: dict[str, dict] | None = None
_index_dirty = True


def _default_cache() -> dict:
    return {
        "_meta": {
            "version": 1,
            "updated_at": 0,
        },
        "tasks": {},
    }


def build_task_key(drive_index: int, remote_path: str) -> str:
    return f"{drive_index}:{str(remote_path or '').rstrip('/')}"


def load_cache() -> dict:
    if not os.path.exists(MEDIA_LIBRARY_CACHE_FILE):
        return _default_cache()
    try:
        with open(MEDIA_LIBRARY_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _default_cache()
        data.setdefault("_meta", {"version": 1, "updated_at": 0})
        data.setdefault("tasks", {})
        return data
    except Exception:
        return _default_cache()


def _save_cache(data: dict):
    os.makedirs(os.path.dirname(MEDIA_LIBRARY_CACHE_FILE), exist_ok=True)
    tmp = MEDIA_LIBRARY_CACHE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, MEDIA_LIBRARY_CACHE_FILE)


def _normalize_item(item: dict) -> dict:
    return {
        "name": str(item.get("name", "") or ""),
        "path": str(item.get("path", "") or ""),
        "pickcode": str(item.get("pickcode", "") or ""),
        "size": int(item.get("size", 0) or 0),
        "id": int(item.get("id", 0) or 0),
        "sha1": str(item.get("sha1", "") or ""),
        "is_dir": bool(item.get("is_dir", False)),
        "parent_id": int(item.get("parent_id", 0) or 0),
    }


def _normalize_items(items: dict) -> dict:
    normalized = {}
    for item_key, item in (items or {}).items():
        if not isinstance(item, dict):
            continue
        normalized[str(item_key)] = _normalize_item(item)
    return normalized


def get_task_items(task_key: str) -> dict:
    cache = load_cache()
    tasks = cache.get("tasks", {})
    task = tasks.get(task_key, {})
    return dict(task.get("items", {}))


def get_task_sha1_set(task_key: str) -> set[str]:
    items = get_task_items(task_key)
    sha1_set = set()
    for item in items.values():
        if item.get("is_dir"):
            continue
        sha1 = str(item.get("sha1", "") or "").upper().strip()
        if sha1:
            sha1_set.add(sha1)
    return sha1_set


def _build_pickcode_index() -> dict[str, dict]:
    """遍历所有task的items，构建 pickcode → {task_key, item_key, item} 索引"""
    cache = load_cache()
    index: dict[str, dict] = {}
    for task_key, task in cache.get("tasks", {}).items():
        for item_key, item in task.get("items", {}).items():
            pc = str(item.get("pickcode", "") or "")
            if pc:
                index[pc] = {"task_key": task_key, "item_key": item_key, "item": dict(item)}
    return index


def get_item_by_pickcode(pickcode: str) -> dict | None:
    """通过 pickcode 查找缓存条目，返回 {task_key, item_key, item} 或 None"""
    global _pickcode_index, _index_dirty
    if _pickcode_index is None or _index_dirty:
        _pickcode_index = _build_pickcode_index()
        _index_dirty = False
    return _pickcode_index.get(pickcode)


def get_item_by_id(item_id: str | int) -> dict | None:
    """通过 id 查找缓存条目，返回 {task_key, item_key, item} 或 None"""
    item_id = str(item_id or "")
    if not item_id:
        return None
    cache = load_cache()
    for task_key, task in cache.get("tasks", {}).items():
        item = (task.get("items", {}) or {}).get(item_id)
        if item:
            return {"task_key": task_key, "item_key": item_id, "item": dict(item)}
    return None


def _mark_index_dirty():
    global _index_dirty
    _index_dirty = True


def _update_task(cache: dict, task_key: str, items: dict, meta: dict | None = None, replace: bool = False):
    now = time.time()
    tasks = cache.setdefault("tasks", {})
    task = tasks.setdefault(task_key, {})
    current_items = {} if replace else dict(task.get("items", {}))
    current_items.update(_normalize_items(items))
    task["updated_at"] = now
    task["item_count"] = len(current_items)
    task["items"] = current_items
    if meta:
        task.update(meta)
    cache["_meta"] = {
        "version": 1,
        "updated_at": now,
    }


def merge_task_items(task_key: str, items: dict, meta: dict | None = None):
    with _lock:
        cache = load_cache()
        _update_task(cache, task_key, items, meta=meta, replace=False)
        _save_cache(cache)
    _mark_index_dirty()


def save_task_snapshot(task_key: str, items: dict, meta: dict | None = None):
    with _lock:
        cache = load_cache()
        _update_task(cache, task_key, items, meta=meta, replace=True)
        _save_cache(cache)
    _mark_index_dirty()


def prune_tasks_by_keys(valid_task_keys: set[str]) -> int:
    with _lock:
        cache = load_cache()
        tasks = cache.setdefault("tasks", {})
        stale_keys = [task_key for task_key in list(tasks.keys()) if task_key not in valid_task_keys]
        if not stale_keys:
            return 0
        for task_key in stale_keys:
            tasks.pop(task_key, None)
        now = time.time()
        cache["_meta"] = {
            "version": 1,
            "updated_at": now,
        }
        _save_cache(cache)
    _mark_index_dirty()
    return len(stale_keys)


def upsert_task_item(task_key: str, item_key: str, item_data: dict, meta: dict | None = None):
    merge_task_items(task_key, {str(item_key): _normalize_item(item_data)}, meta=meta)


def update_task_item_fields(
    task_key: str,
    item_id: str | int,
    *,
    name: str | None = None,
    path: str | None = None,
    meta: dict | None = None,
) -> bool:
    item_id = str(item_id or "")
    if not item_id:
        return False
    updated = False
    with _lock:
        cache = load_cache()
        task = cache.setdefault("tasks", {}).get(task_key)
        if not task:
            return False
        items = task.get("items", {})
        item = items.get(item_id)
        if not item:
            return False
        if name is not None:
            item["name"] = str(name or "")
            updated = True
        if path is not None:
            item["path"] = str(path or "")
            updated = True
        if updated:
            now = time.time()
            task["updated_at"] = now
            if meta:
                task.update(meta)
            cache["_meta"] = {
                "version": 1,
                "updated_at": now,
            }
            _save_cache(cache)
    if updated:
        _mark_index_dirty()
    return updated


def remove_task_items_by_sha1(task_key: str, sha1_values: set[str], meta: dict | None = None) -> int:
    normalized_sha1s = {str(v or "").upper().strip() for v in (sha1_values or set()) if str(v or "").strip()}
    if not normalized_sha1s:
        return 0
    with _lock:
        cache = load_cache()
        tasks = cache.setdefault("tasks", {})
        task = tasks.get(task_key)
        if not task:
            return 0
        items = dict(task.get("items", {}))
        kept = {}
        removed = 0
        for item_key, item in items.items():
            sha1 = str(item.get("sha1", "") or "").upper().strip()
            if sha1 and sha1 in normalized_sha1s:
                removed += 1
                continue
            kept[item_key] = item
        task["items"] = kept
        task["item_count"] = len(kept)
        now = time.time()
        task["updated_at"] = now
        if meta:
            task.update(meta)
        cache["_meta"] = {
            "version": 1,
            "updated_at": now,
        }
        _save_cache(cache)
    _mark_index_dirty()
    return removed


def update_items_path_prefix(task_key: str, old_prefix: str, new_prefix: str, meta: dict | None = None) -> int:
    """更新所有 path 以 old_prefix 开头的条目，将前缀替换为 new_prefix（含文件夹条目自身）"""
    if not old_prefix or old_prefix == new_prefix:
        return 0
    old_prefix = old_prefix.rstrip("/")
    new_prefix = new_prefix.rstrip("/")
    updated = 0
    with _lock:
        cache = load_cache()
        tasks = cache.setdefault("tasks", {})
        task = tasks.get(task_key)
        if not task:
            return 0
        items = task.get("items", {})
        for item_key, item in items.items():
            item_path = str(item.get("path", "") or "")
            if item_path == old_prefix:
                item["path"] = new_prefix
                updated += 1
            elif item_path.startswith(old_prefix + "/"):
                item["path"] = new_prefix + item_path[len(old_prefix):]
                updated += 1
        if updated:
            now = time.time()
            task["updated_at"] = now
            if meta:
                task.update(meta)
            cache["_meta"] = {
                "version": 1,
                "updated_at": now,
            }
            _save_cache(cache)
    if updated:
        _mark_index_dirty()
    return updated


def get_dir_by_parent_and_name(task_key: str, parent_id: int, name: str) -> tuple[int, str] | None:
    """查找 parent_id 下名为 name 的目录，返回 (id, pickcode) 或 None"""
    items = get_task_items(task_key)
    for item in items.values():
        if item.get("is_dir") and item.get("parent_id") == parent_id and item.get("name") == name:
            return int(item.get("id", 0)), str(item.get("pickcode", "") or "")
    return None


def get_dir_by_name(task_key: str, name: str) -> tuple[int, str] | None:
    """按 name 查找目录条目（不限 parent_id），返回 (id, pickcode) 或 None"""
    items = get_task_items(task_key)
    for item in items.values():
        if item.get("is_dir") and item.get("name") == name:
            return int(item.get("id", 0)), str(item.get("pickcode", "") or "")
    return None


def get_dir_by_path(task_key: str, path: str) -> tuple[int, str] | None:
    """按完整 path 查找目录条目，返回 (id, pickcode) 或 None"""
    normalized_path = str(path or "").rstrip("/")
    if not normalized_path:
        return None
    items = get_task_items(task_key)
    for item in items.values():
        item_path = str(item.get("path", "") or "").rstrip("/")
        if item.get("is_dir") and item_path == normalized_path:
            return int(item.get("id", 0)), str(item.get("pickcode", "") or "")
    return None


def upsert_dir_item(task_key: str, item_id: int, name: str, parent_id: int, pickcode: str = "", path: str = ""):
    """写入或更新一个目录条目到媒体库缓存"""
    upsert_task_item(task_key, str(item_id), {
        "id": item_id,
        "name": name,
        "parent_id": parent_id,
        "pickcode": pickcode,
        "path": path,
        "is_dir": True,
        "size": 0,
        "sha1": "",
    })


def remove_items_by_path_prefix(task_key: str, path_prefix: str, meta: dict | None = None) -> int:
    """删除 path 等于 path_prefix 或以 path_prefix/ 开头的所有条目（含文件夹自身）"""
    if not path_prefix:
        return 0
    path_prefix = path_prefix.rstrip("/")
    removed = 0
    with _lock:
        cache = load_cache()
        tasks = cache.setdefault("tasks", {})
        task = tasks.get(task_key)
        if not task:
            return 0
        items = dict(task.get("items", {}))
        kept = {}
        for item_key, item in items.items():
            item_path = str(item.get("path", "") or "").rstrip("/")
            if item_path == path_prefix or item_path.startswith(path_prefix + "/"):
                removed += 1
                continue
            kept[item_key] = item
        if removed:
            task["items"] = kept
            task["item_count"] = len(kept)
            now = time.time()
            task["updated_at"] = now
            if meta:
                task.update(meta)
            cache["_meta"] = {
                "version": 1,
                "updated_at": now,
            }
            _save_cache(cache)
    if removed:
        _mark_index_dirty()
    return removed


def get_task_item_by_id(task_key: str, item_id: str | int) -> dict | None:
    """按 id 查找 task 内单条缓存条目"""
    item_id = str(item_id or "")
    if not item_id:
        return None
    items = get_task_items(task_key)
    item = items.get(item_id)
    return dict(item) if item else None


def remove_task_item_by_id(task_key: str, item_id: str | int, meta: dict | None = None) -> int:
    """按 id 删除单条缓存条目"""
    item_id = str(item_id or "")
    if not item_id:
        return 0
    removed = 0
    with _lock:
        cache = load_cache()
        task = cache.setdefault("tasks", {}).get(task_key)
        if not task:
            return 0
        items = dict(task.get("items", {}))
        if item_id in items:
            items.pop(item_id, None)
            removed = 1
        if removed:
            task["items"] = items
            task["item_count"] = len(items)
            now = time.time()
            task["updated_at"] = now
            if meta:
                task.update(meta)
            cache["_meta"] = {"version": 1, "updated_at": now}
            _save_cache(cache)
    if removed:
        _mark_index_dirty()
    return removed


def remove_task_item_by_pickcode(task_key: str, pickcode: str, meta: dict | None = None) -> int:
    """按 pickcode 删除单条缓存条目"""
    if not pickcode:
        return 0
    removed = 0
    with _lock:
        cache = load_cache()
        task = cache.setdefault("tasks", {}).get(task_key)
        if not task:
            return 0
        items = dict(task.get("items", {}))
        kept = {k: v for k, v in items.items() if str(v.get("pickcode", "") or "") != pickcode}
        removed = len(items) - len(kept)
        if removed:
            task["items"] = kept
            task["item_count"] = len(kept)
            now = time.time()
            task["updated_at"] = now
            if meta:
                task.update(meta)
            cache["_meta"] = {"version": 1, "updated_at": now}
            _save_cache(cache)
    if removed:
        _mark_index_dirty()
    return removed
