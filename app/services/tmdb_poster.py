# app/services/tmdb_poster.py
"""共享的 TMDb 海报/背景图获取逻辑，带缓存避免重复 API 调用。"""

from core.logger import logger

TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

# 简单内存缓存：key=(media_name, media_type, year, tmdb_id) -> url
_cache: dict[tuple, str] = {}


def get_media_backdrop_url(media_name: str, media_type: str = "movie",
                           year: str = "", tmdb_id: str = "") -> str:
    """
    获取媒体"未定义语言"剧照/背景图URL（带缓存）。

    优先使用 TMDB images 接口获取 iso_639_1 为 null 的剧照。
    如果没有找到，回退到默认 poster_path。
    """
    cache_key = (media_name, media_type, year, tmdb_id)
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        import config_manager
        import constants
        from core import tmdb as tmdb_module

        api_key = config_manager.APP_CONFIG.get(constants.CONFIG_OPTION_TMDB_API_KEY)
        if not api_key:
            logger.debug("[TMDb海报] 未配置 TMDB API Key，无法获取背景图")
            _cache[cache_key] = ""
            return ""

        # 先确定 tmdb_id
        resolved_id = None
        if tmdb_id:
            resolved_id = int(tmdb_id)
        else:
            results = tmdb_module.search_media(media_name, api_key, item_type=media_type, year=year)
            if results and len(results) > 0:
                resolved_id = results[0].get("id")

        if resolved_id:
            # 优先获取"未定义语言"(null) 的剧照
            url = tmdb_module.get_null_language_backdrop(resolved_id, media_type, api_key)
            if url:
                _cache[cache_key] = url
                return url

            # 回退：使用 poster 封面图
            if media_type == "movie":
                details = tmdb_module.get_movie_details(resolved_id, api_key, append_to_response=None)
            else:
                details = tmdb_module.get_tv_details(resolved_id, api_key, append_to_response=None)
            if details:
                poster_path = details.get("poster_path")
                if poster_path:
                    url = f"{TMDB_IMAGE_BASE_URL}{poster_path}"
                    _cache[cache_key] = url
                    return url

    except Exception as e:
        logger.debug(f"[TMDb海报] 获取背景图失败: {e}")

    _cache[cache_key] = ""
    return ""
