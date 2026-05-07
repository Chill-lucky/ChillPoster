# app/routers/webhook.py
import os
import json
from fastapi import APIRouter, Request, HTTPException

from app.schemas import WebhookConfigModel
from app.dependencies import webhook_debouncer
from app.routers.config_302 import get_emby_configs_sync
from app.services.task_service import execute_task_logic
from app.services.wechat_service import wechat_notify_service
from core.configs import WEBHOOK_CONFIG_FILE
from core.emby_client import EmbyClient
from core.logger import logger

router = APIRouter(tags=["Webhook"])

@router.get("/api/webhook/config")
def get_webhook_config():
    if os.path.exists(WEBHOOK_CONFIG_FILE):
        try:
            with open(WEBHOOK_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {"enabled": False, "engine": "classic", "preset": "", "mode": "random"}

@router.post("/api/webhook/config")
def save_webhook_config(cfg: WebhookConfigModel):
    try:
        with open(WEBHOOK_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg.model_dump(), f, indent=4, ensure_ascii=False)
        return {"status": "ok"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/webhook")
async def emby_webhook_trigger(request: Request):
    if not os.path.exists(WEBHOOK_CONFIG_FILE):
        return {"status": "ignored", "reason": "No Webhook Config"}
    
    try:
        with open(WEBHOOK_CONFIG_FILE, 'r', encoding='utf-8') as f:
            wh_config = json.load(f)
    except:
        return {"status": "error", "reason": "Config Read Error"}

    if not wh_config.get("enabled", False):
        return {"status": "ignored", "reason": "Webhook Disabled"}

    try:
        content_type = request.headers.get("content-type", "")
        data = {}
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            if 'data' in form:
                data = json.loads(form['data'])
            else:
                data = dict(form)
    except Exception as e:
        return {"status": "error", "reason": f"Payload Error: {e}"}

    event_type = data.get("Event", "")
    allowed_events = ["library.new", "item.added", "library.scan_complete"]
    delete_events = ["item.removed", "library.deleted"]

    if event_type not in allowed_events and event_type not in delete_events:
        return {"status": "ignored", "reason": f"Event '{event_type}' not watched"}

    if event_type in delete_events:
        return {"status": "ok", "action": "ignored_delete_event"}

    item_data = data.get("Item", {})
    target_item_id = item_data.get("Id")
    item_path = item_data.get("Path") 
    
    if not item_path and target_item_id:
        logger.debug(f"[Webhook] payload缺少路径，准备回查: {target_item_id}")

    event_name_map = {
        "library.new": "媒体入库事件",
        "item.added": "新增条目事件",
        "library.scan_complete": "扫描完成事件"
    }
    event_name = event_name_map.get(event_type, "入库事件")
    logger.info(f"[Webhook] 收到{event_name} (ID: {target_item_id})")

    targets = []
    servers = get_emby_configs_sync()

    preset_name = wh_config.get("preset")
    if not preset_name:
        return {"status": "error", "reason": "No Preset Selected"}

    # 遍历服务器，查找该 Webhook 属于哪个库
    for svr_idx, svr in enumerate(servers):
        try:
            if not svr.get('enabled', True):
                continue
            client = EmbyClient(svr['url'], svr['key'], svr.get('public_host'))
            server_libs = client.get_libraries() 
            matched_lib = None
            
            # 1. 尝试直接匹配库ID (如果是 library.new 事件)
            matched_lib = next((l for l in server_libs if str(l['id']) == str(target_item_id)), None)

            # 2. 尝试匹配路径 (如果是 item.added 事件)
            if not matched_lib and item_path:
                norm_item_path = item_path.replace('\\', '/')
                matched_lib = next(
                    (lib for lib in server_libs if lib.get('paths') and 
                     any(norm_item_path.startswith(loc.replace('\\', '/')) for loc in lib.get('paths'))),
                    None
                )

            # 3. 尝试反查 API 获取路径再匹配
            if not matched_lib and target_item_id and not item_path:
                try:
                    full_info = client._request("GET", f"emby/Items/{target_item_id}")
                    fetched_path = full_info.get("Path")
                    if fetched_path:
                        norm_fetched = fetched_path.replace('\\', '/')
                        matched_lib = next(
                            (lib for lib in server_libs if lib.get('paths') and 
                             any(norm_fetched.startswith(loc.replace('\\', '/')) for loc in lib.get('paths'))),
                            None
                        )
                except: pass

            if matched_lib:
                # 发送入库通知
                try:
                    item_name = item_data.get("Name", "未知媒体")
                    item_type = item_data.get("Type", "")
                    year = item_data.get("ProductionYear", "")
                    media_type = "movie" if item_type == "Movie" else "series" if item_type == "Episode" or item_type == "Series" else "other"
                    poster_url = ""
                    season = ""
                    episode = ""
                    original_name = ""# 用于 TMDB 搜索
                    overview = ""
                    rating = ""
                    genres = ""
                    tagline = ""

                    # 从 payload 直接提取额外字段
                    import re as _re
                    server_name = data.get("Server", {}).get("Name", "")
                    original_title = item_data.get("OriginalTitle", "")
                    external_urls = item_data.get("ExternalUrls", [])
                    tmdb_url = next((u.get("Url", "") for u in external_urls if u.get("Name") == "TheMovieDb"), "")
                    premiere_raw = item_data.get("PremiereDate", "")
                    premiere_date = premiere_raw[:10] if premiere_raw else ""
                    _status_raw = item_data.get("Status", "")
                    status = {"Continuing": "连载中", "Ended": "已完结"}.get(_status_raw, _status_raw)
                    _count_match = _re.search(r'(\d+)\s*项', data.get("Title", ""))
                    item_count = _count_match.group(1) if _count_match else ""

                    # 获取媒体详情和海报
                    if target_item_id and media_type in ["movie", "series"]:
                        try:
                            import re as _re2

                            if item_type == "Episode" and item_data.get("SeriesName"):
                                # ── 单集 Episode ──────────────────────────────────────
                                # payload 已有 SeriesName/季号/集号，只调一次 Series API
                                series_name   = item_data.get("SeriesName", "")
                                season        = str(item_data.get("ParentIndexNumber", "?"))
                                episode       = str(item_data.get("IndexNumber", "?"))
                                original_name = item_data.get("OriginalTitle") or series_name
                                item_name     = f"{series_name} S{season}E{episode}"

                                series_id_pl = item_data.get("SeriesId", "")
                                if series_id_pl:
                                    series_info = client.get_item_info(series_id_pl)
                                    if series_info:
                                        overview   = series_info.get("overview", "") or ""
                                        tagline    = series_info.get("tagline", "") or ""
                                        cr         = series_info.get("community_rating")
                                        rating     = str(round(cr, 1)) if cr else ""
                                        genres     = series_info.get("genres", "") or ""
                                        year       = series_info.get("year", year) or year
                                        if not original_name or original_name == series_name:
                                            original_name = series_info.get("original_title") or series_name
                                        poster_url = series_info.get("poster_url") or ""
                                        if not tmdb_url:
                                            tid = series_info.get("tmdb_id", "")
                                            if tid:
                                                tmdb_url = f"https://www.themoviedb.org/tv/{tid}"
                                        if not status:
                                            _s = series_info.get("status", "")
                                            status = {"Continuing": "连载中", "Ended": "已完结"}.get(_s, _s)
                                elif item_data.get("SeriesPrimaryImageTag"):
                                    poster_url = (
                                        f"{client.public_host}/emby/Items/{series_id_pl}"
                                        f"/Images/Primary?tag={item_data['SeriesPrimaryImageTag']}"
                                        f"&quality=90&maxHeight=500"
                                    )

                            elif item_type == "Series":
                                # ── 分组模式 library.new (Type=Series) ───────────────
                                # payload 已含全量元数据，0 次 API 调用
                                original_name = item_data.get("OriginalTitle") or item_data.get("Name", item_name)
                                item_name     = item_data.get("Name", item_name)
                                overview      = item_data.get("Overview", "") or ""
                                tagline       = (item_data.get("Taglines") or [""])[0]
                                cr            = item_data.get("CommunityRating")
                                rating        = str(round(cr, 1)) if cr else ""
                                genres        = ", ".join(item_data.get("Genres", [])) if item_data.get("Genres") else ""
                                year          = item_data.get("ProductionYear", year) or year

                                # 海报
                                img_tags = item_data.get("ImageTags", {})
                                if "Primary" in img_tags:
                                    poster_url = (
                                        f"{client.public_host}/emby/Items/{target_item_id}"
                                        f"/Images/Primary?tag={img_tags['Primary']}&quality=90&maxHeight=500"
                                    )

                                # 集数区间：直接解析 Description（Emby 已算好）
                                desc_str  = data.get("Description", "")
                                ep_range  = ""
                                if desc_str:
                                    first_line = desc_str.split("\n")[0].strip()
                                    if _re2.match(r'S\d+', first_line):
                                        ep_range = first_line
                                if ep_range:
                                    item_name = f"{item_name} {ep_range}"
                                    logger.info(f"[Webhook] library.new 分组通知: {item_name}")
                                else:
                                    # Fallback：查最近入库集数
                                    try:
                                        from app.dependencies import format_episode_range
                                        from collections import defaultdict
                                        recent_eps = client.get_recently_added_episodes(target_item_id)
                                        if recent_eps:
                                            seasons_map = defaultdict(list)
                                            for ep in recent_eps:
                                                seasons_map[ep["season"]].append(ep["episode"])
                                            parts = []
                                            for s in sorted(seasons_map):
                                                r = format_episode_range(seasons_map[s])
                                                parts.append(f"S{str(s).zfill(2)} {r}")
                                            item_name = f"{item_name} {' / '.join(parts)}"
                                            logger.info(f"[Webhook] Series 分组通知(fallback): {item_name}")
                                    except Exception as ep_err:
                                        logger.debug(f"[Webhook] 查询最近集数失败: {ep_err}")

                            else:
                                # ── 电影 Movie ────────────────────────────────────────
                                item_info = client.get_item_info(target_item_id)
                                if item_info:
                                    year          = item_info.get("year", year)
                                    poster_url    = item_info.get("poster_url") or ""
                                    overview      = item_info.get("overview", "") or ""
                                    tagline       = item_info.get("tagline", "") or ""
                                    cr            = item_info.get("community_rating")
                                    rating        = str(round(cr, 1)) if cr else ""
                                    genres        = item_info.get("genres", "") or ""
                                    item_name     = item_info.get("name", item_name)
                                    original_name = item_info.get("original_title") or item_name

                        except Exception as e:
                            logger.debug(f"[Webhook] 获取媒体详情失败: {e}")

                    if media_type in ["movie", "series"]:
                        from app.services.wechat_service import wechat_notify_service
                        from app.services.telegram_service import telegram_notify_service

                        # 剧集且集数可解析 → 走聚合器，合并多集后发一条通知
                        if (media_type == "series"
                                and season not in ("", "?")
                                and episode not in ("", "?")):
                            from app.dependencies import episode_notify_aggregator
                            agg_key = f"{original_name}_S{season}_{matched_lib['name']}"
                            agg_meta = dict(
                                series_name=series_name,
                                season=season,
                                library_name=matched_lib['name'],
                                year=str(year) if year else "",
                                poster_url=poster_url,
                                original_name=original_name,
                                overview=overview,
                                rating=rating,
                                genres=genres,
                                tagline=tagline,
                                server_name=server_name,
                                original_title=original_title,
                                tmdb_url=tmdb_url,
                                premiere_date=premiere_date,
                                status=status,
                                item_count=item_count,
                                server_idx=svr_idx,
                                item_id=str(target_item_id) if target_item_id else "",
                            )
                            episode_notify_aggregator.add(agg_key, episode, agg_meta)
                            logger.info(f"[Webhook] 聚合待发送: {original_name} S{season}E{episode}")
                        else:
                            # 电影 / 无集数信息的剧集 → 直接发
                            notify_kwargs = dict(
                                media_name=item_name,
                                media_type=media_type,
                                library_name=matched_lib['name'],
                                year=str(year) if year else "",
                                poster_url=poster_url,
                                original_name=original_name,
                                overview=overview,
                                rating=rating,
                                genres=genres,
                                tagline=tagline,
                                server_name=server_name,
                                original_title=original_title,
                                tmdb_url=tmdb_url,
                                premiere_date=premiere_date,
                                status=status,
                                item_count=item_count,
                                server_idx=svr_idx,
                                item_id=str(target_item_id) if target_item_id else "",
                            )
                            wechat_notify_service.notify_media_added(**notify_kwargs)
                            telegram_notify_service.notify_media_added(**notify_kwargs)
                except Exception as notify_err:
                    logger.debug(f"[Webhook] 发送入库通知失败: {notify_err}")

                targets.append({
                    "url": svr['url'],
                    "key": svr['key'],
                    "public_host": svr.get('public_host'),
                    "library_id": matched_lib['id'],
                    "library_name": matched_lib['name'],
                    "server_idx": svr_idx,
                })
            else:
                pass

        except Exception as e:
            logger.error(f"-> Error checking server {svr.get('name')}: {e}")

    if not targets:
        return {"status": "ignored", "reason": f"Item not resolved to any library"}

    mode = wh_config.get("mode", "random")
    triggered_count = 0
    
    # 使用防抖器调度任务
    for target in targets:
        lib_id = target['library_id']
        lib_name = target['library_name']

        webhook_debouncer.schedule(
            lib_id,
            execute_task_logic,
            [preset_name, [target], mode, f"Webhook: {lib_name}"],
            display_name=lib_name
        )
        triggered_count += 1

    return {"status": "queued", "targets_debounced": triggered_count}