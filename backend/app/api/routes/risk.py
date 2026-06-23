"""
风险评估路由
================
后续阶段实现健康风险评估、风险等级计算等功能。
"""

from fastapi import APIRouter
from app.models.schemas import RiskDetectRequest, RiskResult
from app.services.risk_service import RiskService

risk_router = APIRouter(prefix="/risk", tags=["risk"])
risk_service = RiskService()

@risk_router.post("/detect", response_model=RiskResult)
async def detect_risk(request: RiskDetectRequest):
    """检测健康风险"""
    result = risk_service.detect_risk(
        symptoms=request.symptoms,
        duration=request.duration
    )
    return result


