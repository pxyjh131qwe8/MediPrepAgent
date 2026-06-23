"""
健康档案路由（预留）
================
后续阶段实现档案 CRUD、档案查询等功能。
"""

from fastapi import APIRouter

record_router = APIRouter(prefix="/record", tags=["record"])


@record_router.get("/")
async def list_records():
    """预留：获取健康档案列表"""
    return {"message": "record endpoint (TODO)", "data": []}
