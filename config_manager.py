# config_manager.py
import os
import json
import time
import logging
import constants  # 引用下面的 constants.py

logger = logging.getLogger(__name__)

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config", "settings.json")

# 带 TTL 的配置缓存
_settings_cache = None
_settings_cache_time = 0
_SETTINGS_TTL = 5  # 5 秒缓存

def load_settings():
    """从 settings.json 加载配置，带 5 秒内存缓存"""
    global _settings_cache, _settings_cache_time
    now = time.time()
    if _settings_cache is not None and (now - _settings_cache_time) < _SETTINGS_TTL:
        return _settings_cache
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                _settings_cache = json.load(f)
                _settings_cache_time = now
                return _settings_cache
        except Exception as e:
            logger.error(f"读取配置文件失败: {e}")
    return {}

class ConfigProxy(dict):
    """
    一个智能字典，自动把 tmdb.py 请求的键名映射到 settings.json 的键名
    """
    def get(self, key, default=None):
        settings = load_settings()

        # 映射表：左边是 tmdb.py 要的，右边是 settings.json 里的
        key_map = {
            constants.CONFIG_OPTION_TMDB_API_KEY: "tmdb_key",      # 映射 tmdb_key
            constants.CONFIG_OPTION_NETWORK_HTTP_PROXY: "proxy_url", # 映射 proxy_url
            constants.CONFIG_OPTION_TMDB_API_BASE_URL: "tmdb_api_base_url" # 映射基础URL
        }

        real_key = key_map.get(key, key)
        return settings.get(real_key, default)

    def __getitem__(self, key):
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

# 初始化全局配置对象
APP_CONFIG = ConfigProxy()

def get_proxies_for_requests():
    """专门为 tmdb.py 提供代理格式"""
    proxy_url = APP_CONFIG.get(constants.CONFIG_OPTION_NETWORK_HTTP_PROXY)
    if proxy_url:
        return {"http": proxy_url, "https": proxy_url}
    return None
