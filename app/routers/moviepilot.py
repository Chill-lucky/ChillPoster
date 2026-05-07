# app/routers/moviepilot.py
# MoviePilot 配置与订阅代理

import os
import json
import time
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import httpx

logger = logging.getLogger("MoviePilot")
router = APIRouter(prefix="/api/moviepilot", tags=["MoviePilot"])

CONFIG_PATH = os.path.join("config", "moviepilot.json")


# ========== 数据模型 ==========

class MoviePilotConfigModel(BaseModel):
    mp_url: str = ""
    mp_username: str = ""
    mp_password: str = ""

class SubscribeRequest(BaseModel):
    tmdbid: int
    type_name: str = "movie"  # movie / tv
    season: Optional[int] = None
    name: Optional[str] = None
    year: Optional[str] = None


# ========== 配置读写 ==========

def _load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"mp_url": "", "mp_username": "", "mp_password": ""}

def _save_config(cfg: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ========== MoviePilot API 客户端 ==========

class MoviePilotClient:
    """管理 MoviePilot 认证和 API 调用"""
    _token: Optional[str] = None
    _token_expires: float = 0
    _last_error: Optional[str] = None  # 记录最近一次错误

    @classmethod
    def _get_base_url(cls) -> str:
        cfg = _load_config()
        return cfg.get("mp_url", "").rstrip("/")

    @classmethod
    async def login(cls) -> Optional[str]:
        """登录 MP 获取 Token，缓存 24h"""
        cls._last_error = None
        if cls._token and time.time() < cls._token_expires:
            return cls._token

        cfg = _load_config()
        url = cfg.get("mp_url", "").rstrip("/")
        if not url:
            cls._last_error = "未配置 MoviePilot 地址"
            return None

        username = cfg.get("mp_username", "")
        password = cfg.get("mp_password", "")
        if not username or not password:
            cls._last_error = "未填写用户名或密码"
            return None

        try:
            async with httpx.AsyncClient(verify=False, timeout=15) as client:
                # MP 登录使用 OAuth2 表单格式
                resp = await client.post(
                    f"{url}/api/v1/login/access-token",
                    data={"username": username, "password": password},
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    cls._token = data.get("token") or data.get("access_token")
                    if not cls._token:
                        cls._last_error = f"登录成功但未获取到 token，响应: {str(data)[:200]}"
                        return None
                    cls._token_expires = time.time() + 86400  # 24h
                    logger.info("MP 登录成功")
                    return cls._token
                elif resp.status_code == 401:
                    cls._last_error = "用户名或密码错误 (401)"
                    return None
                elif resp.status_code == 422:
                    cls._last_error = f"请求格式错误 (422): {resp.text[:200]}"
                    return None
                else:
                    cls._last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    return None
        except httpx.ConnectError as e:
            cls._last_error = f"连接失败，请检查地址是否正确: {e}"
            return None
        except httpx.TimeoutException:
            cls._last_error = "连接超时，请检查 MoviePilot 是否在线以及网络连通性"
            return None
        except Exception as e:
            cls._last_error = f"连接异常: {type(e).__name__}: {e}"
            return None

    @classmethod
    async def _request(cls, method: str, path: str, json_data: dict = None, params: dict = None) -> dict:
        """向 MP 发送带认证的请求"""
        url = cls._get_base_url()
        if not url:
            return {"error": "未配置 MoviePilot 地址"}

        token = await cls.login()
        if not token:
            return {"error": f"MoviePilot 登录失败: {cls._last_error}"}

        headers = {"Authorization": f"Bearer {token}"}
        try:
            async with httpx.AsyncClient(verify=False, timeout=15) as client:
                resp = await client.request(
                    method, f"{url}{path}",
                    headers=headers, json=json_data, params=params
                )
                # 401 时自动重试
                if resp.status_code == 401:
                    cls._token = None
                    token = await cls.login()
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        resp = await client.request(
                            method, f"{url}{path}",
                            headers=headers, json=json_data, params=params
                        )
                if resp.status_code < 400:
                    return resp.json() if resp.text else {}
                else:
                    logger.error(f"MP API {method} {path} -> {resp.status_code}: {resp.text[:500]}")
                    return {"error": f"MP API {resp.status_code}: {resp.text[:200]}"}
        except Exception as e:
            return {"error": f"MP 请求异常: {type(e).__name__}: {e}"}


# ========== API 端点 ==========

@router.get("/config")
async def get_mp_config():
    cfg = _load_config()
    # 不返回密码明文
    return {
        "mp_url": cfg.get("mp_url", ""),
        "mp_username": cfg.get("mp_username", ""),
        "mp_password": cfg.get("mp_password", ""),
    }

@router.post("/config")
async def save_mp_config(cfg: MoviePilotConfigModel):
    _save_config(cfg.model_dump())
    # 配置变更时清除旧 token
    MoviePilotClient._token = None
    return {"status": "ok"}

@router.post("/test")
async def test_mp_connection():
    token = await MoviePilotClient.login()
    if token:
        return {"status": "ok", "message": "连接成功"}
    error_msg = MoviePilotClient._last_error or "连接失败，请检查配置"
    return {"status": "error", "message": error_msg}

@router.post("/subscribe")
async def mp_subscribe(req: SubscribeRequest):
    # MP 订阅 API 的 type 字段实际需要中文: "电影" / "电视剧"
    mp_type = "电视剧" if req.type_name == "tv" else "电影"
    body = {
        "tmdbid": req.tmdbid,
        "type": mp_type,
    }
    if req.name:
        body["name"] = req.name
    if req.year:
        body["year"] = req.year
    if req.season:
        body["season"] = req.season

    result = await MoviePilotClient._request("POST", "/api/v1/subscribe/", json_data=body)
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return result

@router.delete("/subscribe")
async def mp_unsubscribe(tmdbid: int = Query(...), type_name: str = Query("movie"), season: Optional[int] = Query(None)):
    media_id = f"tmdb:{tmdbid}" if type_name == "movie" else f"tmdb:{tmdbid}"
    params = {"season": season} if season else {}
    result = await MoviePilotClient._request("DELETE", f"/api/v1/subscribe/media/{media_id}", params=params)
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return result

@router.get("/subscribe/check")
async def mp_check_subscribe(tmdbid: int = Query(...), type_name: str = Query("movie"), season: Optional[int] = Query(None)):
    media_id = f"tmdb:{tmdbid}"
    params = {"season": season} if season else {}
    result = await MoviePilotClient._request("GET", f"/api/v1/subscribe/media/{media_id}", params=params)
    if result.get("error"):
        return {"subscribed": False}
    # MP 返回数据中有 id 说明已订阅
    return {"subscribed": bool(result.get("id"))}
