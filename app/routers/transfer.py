# app/routers/transfer.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.transfer_service import transfer_service
from app.routers.wechat_notify import send_to_all_channels

router = APIRouter(prefix="/api/transfer", tags=["Transfer"])


class ManualTransferRequest(BaseModel):
    link: str = ""


@router.post("/manual")
async def manual_transfer(req: ManualTransferRequest):
    """手动转存 115 分享链接"""
    link = (req.link or "").strip()
    if not link:
        raise HTTPException(status_code=400, detail="链接不能为空")

    # 支持一次粘贴多行（多条链接）
    lines = [l.strip() for l in link.splitlines() if l.strip()]
    if not lines:
        raise HTTPException(status_code=400, detail="未找到有效链接")

    # 也尝试从整个文本中提取链接
    all_links = []
    for line in lines:
        extracted = transfer_service.extract_links(line)
        if extracted:
            all_links.extend(extracted)
        else:
            # 可能是纯 share_code 格式
            all_links.append(line)

    results = []
    for lnk in all_links:
        result = await transfer_service.process_link(lnk, source="manual")
        results.append(result)
        # 发送转存通知到所有启用的渠道
        send_to_all_channels(
            title=result.get("status", "转存"),
            description=result.get("message", ""),
            notify_type="resource_transfer",
        )

    if len(results) == 1:
        return results[0]
    return {"results": results}


@router.get("/history")
async def get_transfer_history():
    """获取转存历史记录"""
    return transfer_service.get_history()


@router.delete("/history")
async def clear_transfer_history():
    """清空转存历史记录"""
    transfer_service.clear_history()
    return {"status": "ok"}
