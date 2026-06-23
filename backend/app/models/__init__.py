"""
MediPrepAgent - Data Models Package
"""
from .schemas import (
    HealthConsultRequest,
    DepartmentRecommendRequest,
    RiskDetectRequest,
    ReportAnalyzeRequest,
    RiskResult,
    DepartmentResult,
    HealthConsultResponse,
)
from .db_models import Base, HealthRecord, ReportRecord

__all__ = [
    "HealthConsultRequest",
    "DepartmentRecommendRequest",
    "RiskDetectRequest",
    "ReportAnalyzeRequest",
    "RiskResult",
    "DepartmentResult",
    "HealthConsultResponse",
    "Base",
    "HealthRecord",
    "ReportRecord",
]
