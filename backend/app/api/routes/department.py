"""
科室相关路由
================
后续阶段实现科室 CRUD、科室匹配等功能。
"""

from fastapi import APIRouter
from app.models.schemas import DepartmentRecommendRequest
from app.services.department_service import DepartmentService

department_router = APIRouter(prefix="/department", tags=["department"])
department_service = DepartmentService()


@department_router.post("/recommend")
async def recommend_department(request: DepartmentRecommendRequest):
    """根据症状推荐科室（POST规则化）"""
    return department_service.recommend_department(request.symptoms)