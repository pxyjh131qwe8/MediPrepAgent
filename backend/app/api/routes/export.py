"""
数据导出路由（预留）
================
后续阶段实现 PDF/Excel 等格式的数据导出功能。
"""

from fastapi import APIRouter

export_router = APIRouter(prefix="/export", tags=["export"])


@export_router.get("/")
async def list_exports():
    """预留：获取导出任务列表"""
    return {"message": "export endpoint (TODO)", "data": []}
