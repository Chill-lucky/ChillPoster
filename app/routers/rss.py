# app/routers/rss.py
import os
import time
import json
import shutil
from fastapi import APIRouter, Body, HTTPException
from apscheduler.triggers.cron import CronTrigger

from app.schemas import RssGlobalConfig, RssTaskModel, UpdateRssTaskRequest, ToggleTaskRequest
from core.configs import RSS_CONFIG_FILE, RSS_TASKS_FILE, CONFIG_FILE
from core.emby_client import EmbyClient
from app.dependencies import RSS_JOB_QUEUE
from app.routers.config_302 import get_emby_config_by_index_sync
from app.services.task_service import task_service_instance
from core.logger import logger

router = APIRouter(tags=["RSS"])

RUNTIME_STATE_KEYS = {"last_entries", "entry_tmdb_map", "last_sync_at"}

def _build_standard_rss_config() -> dict:
    try:
        from app.routers.config_302 import get_config_302_sync

        cfg302 = get_config_302_sync()
        topology = cfg302.get("standard_topology") if isinstance(cfg302, dict) else None
        if not isinstance(topology, dict):
            return {"source_root": "", "link_root": ""}
        return {
            "source_root": topology.get("local_media_dir", "") or "",
            "link_root": topology.get("local_real_library_dir", "") or "",
        }
    except Exception:
        return {"source_root": "", "link_root": ""}


@router.post("/api/rss/save_config")
def save_rss_config(cfg: RssGlobalConfig):
    save_data = cfg.model_dump()
    standard_cfg = _build_standard_rss_config()
    if standard_cfg.get("link_root"):
        save_data["source_root"] = standard_cfg.get("source_root", save_data.get("source_root", ""))
        save_data["link_root"] = standard_cfg.get("link_root", save_data.get("link_root", ""))
    with open(RSS_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=4, ensure_ascii=False)
    return {"status": "ok", "message": "RSS 路径已绑定到标准拓扑"}

@router.get("/api/rss/config")
def get_rss_config():
    standard_cfg = _build_standard_rss_config()
    if os.path.exists(RSS_CONFIG_FILE):
        with open(RSS_CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            if standard_cfg.get("link_root"):
                data["source_root"] = standard_cfg.get("source_root", data.get("source_root", ""))
                data["link_root"] = standard_cfg.get("link_root", data.get("link_root", ""))
            return data
    return standard_cfg

@router.get("/api/rss/tasks")
def get_rss_tasks():
    if os.path.exists(RSS_TASKS_FILE):
        with open(RSS_TASKS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    return []

@router.post("/api/rss/create_task")
def create_rss_task(req: RssTaskModel):
    tasks = []
    if os.path.exists(RSS_TASKS_FILE):
        with open(RSS_TASKS_FILE, 'r', encoding='utf-8') as f: tasks = json.load(f)
    task_id = f"rss_{int(time.time())}"
    task_data = req.model_dump()
    task_data['id'] = task_id
    task_data.setdefault('last_entries', [])
    task_data.setdefault('entry_tmdb_map', {})
    task_data.setdefault('last_sync_at', None)
    tasks.append(task_data)
    with open(RSS_TASKS_FILE, 'w', encoding='utf-8') as f: 
        json.dump(tasks, f, indent=4, ensure_ascii=False)
    try:
        job_fn = lambda tid=task_id: RSS_JOB_QUEUE.put(tid)
        task_service_instance.scheduler.add_job(job_fn, CronTrigger.from_crontab(task_data['cron']), id=task_id, name=f"RSS: {task_data['name']}", replace_existing=True)
    except: pass
    return {"status": "ok"}

@router.post("/api/rss/update_task")
def update_rss_task(req: UpdateRssTaskRequest):
    if not os.path.exists(RSS_TASKS_FILE): raise HTTPException(status_code=404)
    try:
        with open(RSS_TASKS_FILE, "r", encoding="utf-8") as f:
            tasks = json.load(f)
        
        found = False
        req_data = req.model_dump()
        for i, t in enumerate(tasks):
            if t['id'] == req.id:
                merged = dict(req_data)
                for key in RUNTIME_STATE_KEYS:
                    if key in t:
                        merged[key] = t[key]
                tasks[i] = merged
                found = True
                break
        
        if not found: raise HTTPException(status_code=404, detail="Task not found")

        with open(RSS_TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=4, ensure_ascii=False)

        if task_service_instance.scheduler.get_job(req.id): task_service_instance.scheduler.remove_job(req.id)
        
        if req.enabled:
            job_fn = lambda tid=req.id: RSS_JOB_QUEUE.put(tid)
            task_service_instance.scheduler.add_job(job_fn, CronTrigger.from_crontab(req.cron), id=req.id, name=f"RSS: {req.name}", replace_existing=True)
            
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/rss/run_now")
def run_rss_now(payload: dict = Body(...)):
    tid = payload.get('id')
    RSS_JOB_QUEUE.put(tid)
    return {"status": "triggered"}

@router.post("/api/rss/delete_task")
def delete_rss_task(payload: dict = Body(...)):
    tid = payload.get('id')
    delete_files = payload.get('delete_files', False) 

    task_to_delete = None
    remaining_tasks = []

    if os.path.exists(RSS_TASKS_FILE):
        with open(RSS_TASKS_FILE, 'r', encoding='utf-8') as f: 
            tasks = json.load(f)
        for t in tasks:
            if t['id'] == tid:
                task_to_delete = t
            else:
                remaining_tasks.append(t)
        
        with open(RSS_TASKS_FILE, 'w', encoding='utf-8') as f: 
            json.dump(remaining_tasks, f, indent=4, ensure_ascii=False)

    if task_service_instance.scheduler.get_job(tid):
        task_service_instance.scheduler.remove_job(tid)

    if task_to_delete:
        task_name = task_to_delete['name']
        try:
            srv_idx = task_to_delete.get('target_server_idx', 0)
            server = get_emby_config_by_index_sync(srv_idx)
            if server and server.get('enabled', True):
                client = EmbyClient(server['url'], server['key'], server.get('public_host'))

                all_libs = client.get_libraries()
                target_lib = next((l for l in all_libs if l['name'] == task_name), None)

                if target_lib:
                    client.delete_library(target_lib['id'])
        except Exception as e:
            logger.error(f"[Delete Error] 删除库出错: {e}")

        if delete_files:
            try:
                target_path = None
                if os.path.exists(RSS_CONFIG_FILE):
                    with open(RSS_CONFIG_FILE, 'r', encoding='utf-8') as f: 
                        rss_cfg = json.load(f)
                    link_root = rss_cfg.get('link_root')
                    if link_root:
                        target_path = os.path.join(link_root, task_name)
                
                if target_path and os.path.exists(target_path):
                    shutil.rmtree(target_path)
            except Exception as e:
                logger.error(f"[Delete Error] 删除文件失败: {e}")

    return {"status": "ok"}

@router.post("/api/rss/toggle_task")
def toggle_rss_task_endpoint(req: ToggleTaskRequest):
    if not os.path.exists(RSS_TASKS_FILE): raise HTTPException(status_code=404)
    try:
        with open(RSS_TASKS_FILE, "r", encoding="utf-8") as f:
            tasks = json.load(f)

        target = next((t for t in tasks if t.get("id") == req.id), None)
        if not target: raise HTTPException(status_code=404)

        target['enabled'] = req.enabled

        with open(RSS_TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=4, ensure_ascii=False)

        if req.enabled:
             job_fn = lambda tid=target['id']: RSS_JOB_QUEUE.put(tid)
             task_service_instance.scheduler.add_job(job_fn, CronTrigger.from_crontab(target['cron']), id=target['id'], name=f"RSS: {target['name']}", replace_existing=True)
        else:
            if task_service_instance.scheduler.get_job(req.id):
                task_service_instance.scheduler.remove_job(req.id)

        return {"status": "ok", "enabled": req.enabled}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))