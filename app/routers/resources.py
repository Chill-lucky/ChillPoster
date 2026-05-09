# app/routers/resources.py
import os
import json
import base64
import shutil
import uuid
import threading
import gc
from io import BytesIO
from PIL import Image
from concurrent.futures import as_completed

from fastapi import APIRouter, UploadFile, File, Body, HTTPException

from app.schemas import PreviewRequest, SuiteBackupRequest, SuiteRestoreRequest, SuiteContentRequest
from app.dependencies import GLOBAL_EXECUTOR, ACTIVE_TASKS, update_task_progress, global_translations
from core.configs import FONTS_DIR, LAYOUTS_DIR, TEMPLATES_DIR, BACKUPS_DIR, TRANSLATIONS_FILE
from core.engine import PosterEngine
from core.emby_client import EmbyClient
from core.logger import logger

router = APIRouter(tags=["Resources"])

# --- 字体 ---
@router.get("/api/fonts")
def get_fonts():
    fonts = [f for f in os.listdir(FONTS_DIR) if f.lower().endswith(('.ttf', '.otf'))] if os.path.exists(FONTS_DIR) else []
    return {"fonts": fonts}

@router.post("/api/upload_font")
async def upload_font(file: UploadFile = File(...)):
    safe_name = os.path.basename(file.filename)
    if ".." in safe_name or not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = os.path.join(FONTS_DIR, safe_name)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"status": "ok"}

@router.post("/api/delete_font")
def delete_font(payload: dict = Body(...)):
    filename = payload.get("filename")
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = os.path.join(FONTS_DIR, filename)
    if not os.path.abspath(path).startswith(os.path.abspath(FONTS_DIR)):
        raise HTTPException(status_code=400, detail="Invalid path")
    if os.path.exists(path):
        os.remove(path)
        return {"status": "ok"}
    raise HTTPException(status_code=404)

# --- 布局与模板 ---
def _list_layout_files() -> dict:
    layout_files = {}
    if os.path.exists(LAYOUTS_DIR):
        for filename in os.listdir(LAYOUTS_DIR):
            if filename.endswith(".py") and filename != "__init__.py":
                layout_files[filename[:-3]] = filename
            elif filename.endswith(".pyc") and filename != "__init__.pyc":
                layout_files.setdefault(filename[:-4], filename)
    return layout_files


@router.get("/api/layouts")
def get_layouts():
    layouts_data = {}
    for module_name, filename in _list_layout_files().items():
        file_path = os.path.join(LAYOUTS_DIR, filename)
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, 'get_schema'):
                layouts_data[module_name] = module.get_schema()
        except Exception as e:
            logger.error(f"❌ 加载布局失败 [{filename}]: {e}")
    return {"layouts": layouts_data}

@router.get("/api/templates_v2")
def get_templates_v2():
    layouts = list(_list_layout_files())
    all_presets = []
    if os.path.exists(TEMPLATES_DIR):
        for f in os.listdir(TEMPLATES_DIR):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(TEMPLATES_DIR, f), "r", encoding="utf-8") as file:
                        data = json.load(file)
                        preset_obj = {"filename": f, "name": data.get("name", f), "engine": data.get("engine", "classic"), "config": data.get("config", {})}
                        img_name = f.replace(".json", ".jpg")
                        if os.path.exists(os.path.join(TEMPLATES_DIR, img_name)): 
                            preset_obj["image"] = f"/templates/{img_name}"
                        all_presets.append(preset_obj)
                except: pass
    result = []
    for ly in sorted(layouts):
        matched = [p for p in all_presets if p["engine"] == ly]
        result.append({"layout": ly, "presets": matched})
    return {"data": result, "all_raw": all_presets}

@router.post("/api/save_template")
def save_template(payload: dict = Body(...)):
    filename = payload.get("filename")
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not filename.endswith(".json"): filename += ".json"
    path = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.abspath(path).startswith(os.path.abspath(TEMPLATES_DIR)):
        raise HTTPException(status_code=400, detail="Invalid path")
    data = {"name": payload.get("name", filename), "engine": payload.get("engine", "classic"), "config": payload.get("config", {})}
    
    # 保存预览图
    image_data_b64 = payload.get("image_data")
    if image_data_b64:
        try:
            encoded = image_data_b64.split(",", 1)[1] if "," in image_data_b64 else image_data_b64
            img_bytes = base64.b64decode(encoded)
            img_path = os.path.join(TEMPLATES_DIR, filename.replace(".json", ".jpg"))
            with Image.open(BytesIO(img_bytes)) as img:
                if img.mode != 'RGB': img = img.convert('RGB')
                img.thumbnail((640, 360)) 
                img.save(img_path, format='JPEG', quality=80)
        except: pass
        
    try:
        with open(path, "w", encoding="utf-8") as f: 
            json.dump(data, f, ensure_ascii=False, indent=4)
        return {"status": "ok"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/delete_template")
def delete_template(payload: dict = Body(...)):
    filename = payload.get("filename")
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.abspath(path).startswith(os.path.abspath(TEMPLATES_DIR)):
        raise HTTPException(status_code=400, detail="Invalid path")
    if os.path.exists(path):
        os.remove(path)
        img_path = os.path.join(TEMPLATES_DIR, filename.replace(".json", ".jpg"))
        if os.path.exists(img_path): os.remove(img_path)
        return {"status": "ok"}
    raise HTTPException(status_code=404)

@router.post("/api/upload_template")
async def upload_template(file: UploadFile = File(...)):
    safe_name = os.path.basename(file.filename)
    if not safe_name.lower().endswith('.json'): raise HTTPException(status_code=400)
    file_path = os.path.join(TEMPLATES_DIR, safe_name)
    with open(file_path, "wb") as buffer: 
        shutil.copyfileobj(file.file, buffer)
    return {"status": "ok"}

# --- 预览与应用 ---
@router.post("/api/preview")
def preview(req: PreviewRequest):
    client = EmbyClient(req.url, req.key, req.public_host)
    engine = PosterEngine(fonts_dir=FONTS_DIR, layouts_dir=LAYOUTS_DIR)
    
    if req.custom_assets and (req.custom_assets.get('bg_url') or req.custom_assets.get('posters')):
        assets = req.custom_assets
        if 'count' not in assets or assets['count'] == 0: 
            assets['count'] = client.get_library_count(req.library_id)
    else:
        p_limit = int(req.config.get('poster_count', 6))
        b_limit = int(req.config.get('backdrop_count', 1))
        assets = client.get_assets(req.library_id, mode=req.mode, poster_limit=p_limit, backdrop_limit=b_limit)
        
    img_b64 = engine.draw(req.config, assets)
    gc.collect()
    
    mime_type = "image/jpeg"
    if img_b64.startswith("iVBOR"): mime_type = "image/png" # PNG头
    elif img_b64.startswith("R0lGOD"): mime_type = "image/gif"
    
    return {"image": f"data:{mime_type};base64,{img_b64}"}

@router.post("/api/apply")
def apply(req: PreviewRequest):
    client = EmbyClient(req.url, req.key, req.public_host)
    img_data = None
    if req.image_data:
        try:
            b64_str = req.image_data.split(",")[-1]
            img_data = base64.b64decode(b64_str)
        except: pass
        
    if not img_data:
        # 如果前端没有传图片数据，后端现场生成
        engine = PosterEngine(fonts_dir=FONTS_DIR, layouts_dir=LAYOUTS_DIR)
        if req.custom_assets and (req.custom_assets.get('bg_url') or req.custom_assets.get('posters')):
             assets = req.custom_assets
             if 'count' not in assets or assets['count'] == 0: 
                 assets['count'] = client.get_library_count(req.library_id)
        else:
             p_limit = int(req.config.get('poster_count', 6))
             b_limit = int(req.config.get('backdrop_count', 1))
             assets = client.get_assets(req.library_id, mode=req.mode, poster_limit=p_limit, backdrop_limit=b_limit)
        img_b64 = engine.draw(req.config, assets)
        try: img_data = base64.b64decode(img_b64)
        except: raise HTTPException(status_code=500, detail="Generate Failed")
        
    gc.collect()
    if client.upload_cover(req.library_id, img_data): return {"status": "ok"}
    raise HTTPException(status_code=500, detail="Upload Failed")

# --- 翻译配置 ---
@router.get("/api/translations")
def get_translations(): 
    return global_translations

@router.post("/api/save_translations")
def save_translations(payload: dict = Body(...)):
    new_data = payload.get("translations", {})
    # 更新内存
    global_translations.clear()
    global_translations.update(new_data)
    try:
        with open(TRANSLATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=4)
        return {"status": "ok"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- 备份/快照 ---
@router.get("/api/list_suites")
def list_suites():
    suites = []
    if os.path.exists(BACKUPS_DIR):
        for d in os.listdir(BACKUPS_DIR):
            dir_path = os.path.join(BACKUPS_DIR, d)
            if os.path.isdir(dir_path):
                try:
                    count = len([f for f in os.listdir(dir_path) if f.endswith('.jpg')])
                    ctime = os.path.getctime(dir_path)
                    suites.append({"name": d, "count": count, "time": ctime})
                except: pass
    suites.sort(key=lambda x: x['time'], reverse=True)
    return {"suites": suites}

@router.post("/api/get_suite_content")
def get_suite_content(req: SuiteContentRequest):
    suite_dir = os.path.join(BACKUPS_DIR, req.suite_name)
    if not os.path.exists(suite_dir): return {"images": []}
    files = [f for f in os.listdir(suite_dir) if f.endswith(".jpg")]
    images = [{"id": f.replace(".jpg", ""), "url": f"/backups/{req.suite_name}/{f}"} for f in files]
    return {"images": images}

@router.post("/api/delete_suite")
def delete_suite(payload: dict = Body(...)):
    suite_name = payload.get("suite_name")
    if not suite_name or ".." in suite_name: raise HTTPException(status_code=400)
    suite_dir = os.path.join(BACKUPS_DIR, suite_name)
    if os.path.exists(suite_dir):
        shutil.rmtree(suite_dir)
        return {"status": "ok"}
    raise HTTPException(status_code=404)

@router.post("/api/create_suite")
def create_suite(req: SuiteBackupRequest):
    if not req.suite_name or ".." in req.suite_name: raise HTTPException(status_code=400)
    suite_dir = os.path.join(BACKUPS_DIR, req.suite_name)
    if not os.path.exists(suite_dir): os.makedirs(suite_dir)
    
    run_id = str(uuid.uuid4())
    
    def run_backup():
        base_name = f"备份: {req.suite_name}"
        update_task_progress(run_id, base_name, 0, "running")
        try:
            client = EmbyClient(req.url, req.key, req.public_host)
            libs = client.get_libraries() 
            total = len(libs)
            
            def process_save_cover(lib):
                try:
                    lib_id = lib['id']
                    img_data = client.download_cover(lib_id)
                    if img_data:
                        with open(os.path.join(suite_dir, f"{lib_id}.jpg"), "wb") as f: f.write(img_data)
                        return True
                except: pass
                return False
                
            futures = [GLOBAL_EXECUTOR.submit(process_save_cover, lib) for lib in libs]
            
            for i, future in enumerate(as_completed(futures)):
                if ACTIVE_TASKS.get(run_id, {}).get("cancel_requested"):
                    for f in futures: f.cancel()
                    update_task_progress(run_id, f"{base_name} (已停止)", int(((i) / total) * 100), "error")
                    return
                future.result()
                percent = int(((i + 1) / total) * 100)
                update_task_progress(run_id, f"{base_name} (共{total}个)", percent, "running")
            
            update_task_progress(run_id, f"{base_name} (完成)", 100, "finished")
            gc.collect() 
        except Exception as e: 
            update_task_progress(run_id, f"{base_name} (失败)", 0, "error")
            
    threading.Thread(target=run_backup).start()
    return {"status": "ok", "run_id": run_id}

@router.post("/api/restore_suite")
def restore_suite(req: SuiteRestoreRequest):
    suite_dir = os.path.join(BACKUPS_DIR, req.suite_name)
    if not os.path.exists(suite_dir): raise HTTPException(status_code=404)
    client = EmbyClient(req.url, req.key, req.public_host)
    files = [f for f in os.listdir(suite_dir) if f.endswith(".jpg")]
    
    if not files: return {"status": "ok", "restored": 0}
    
    run_id = str(uuid.uuid4())
    
    def run_restore():
        task_name = f"恢复: {req.suite_name}"
        update_task_progress(run_id, task_name, 0, "running")
        total = len(files)
        target_set = set(req.target_ids) if req.target_ids else None
        
        def process_restore_cover(filename):
            lib_id = filename.replace(".jpg", "")
            if target_set is not None and lib_id not in target_set: return False
            file_path = os.path.join(suite_dir, filename)
            try:
                with Image.open(file_path) as img:
                    if img.mode != 'RGB': img = img.convert('RGB')
                    output = BytesIO()
                    img.save(output, format='JPEG', quality=75)
                    compressed = output.getvalue()
                if client.upload_cover(lib_id, compressed): return True
            except: pass
            return False
            
        futures = [GLOBAL_EXECUTOR.submit(process_restore_cover, f) for f in files]
        
        for i, future in enumerate(as_completed(futures)):
            if ACTIVE_TASKS.get(run_id, {}).get("cancel_requested"):
                for f in futures: f.cancel()
                update_task_progress(run_id, f"{task_name} (已停止)", int(((i) / total) * 100), "error")
                return
            future.result()
            percent = int(((i + 1) / total) * 100)
            update_task_progress(run_id, task_name, percent, "running")
            
        update_task_progress(run_id, task_name, 100, "finished")
        gc.collect()
        
    threading.Thread(target=run_restore).start()
    return {"status": "ok", "run_id": run_id}