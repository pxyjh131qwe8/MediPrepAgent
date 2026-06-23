"""
报告生成路由（预留）
================
后续阶段实现 LLM 驱动的健康报告生成功能。
"""

from fastapi import APIRouter

report_router = APIRouter(prefix="/report", tags=["report"])


@report_router.get("/")
async def list_reports():
    """预留：获取报告列表"""
    return {"message": "report endpoint (TODO)", "data": []}
