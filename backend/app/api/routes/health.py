"""
健康咨询路由
==========
提供 /health/consult 。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.schemas import HealthConsultRequest, HealthConsultResponse
from app.services.health_service import HealthService
from app.config import async_engine, get_database

# 创建独立的路由器，prefix 由 main.py 统一管理
health_router = APIRouter(tags=["health"])

health_service = HealthService()

@health_router.post("/consult", response_model=HealthConsultResponse)
async def consult_health_api(request: HealthConsultRequest, db: AsyncSession = Depends(get_database)):
    """健康咨询接口"""
    return await health_service.consult_health(request, db=db)