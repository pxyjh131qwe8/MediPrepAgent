"""
Pydantic schemas for MediPrepAgent - Request/Response models.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================
# Request Models
# ============================================================

class HealthConsultRequest(BaseModel):
    """用户提交健康咨询请求"""
    age: Optional[int] = None
    gender: Optional[str] = None
    symptoms: str
    duration: Optional[str] = None
    medical_history: Optional[str] = None
    medication_history: Optional[str] = None
    allergy_history: Optional[str] = None
    goal: Optional[str] = None
    
    # 新增
    thread_id: Optional[str] = "default_thread_id"
    # 显式控制是否合并历史上下文
    use_saved_context: bool = False
    
# 新增
class HealthContextUpdateRequest(BaseModel):
    thread_id: str

    age: Optional[int] = None
    gender: Optional[str] = None
    latest_symptoms: Optional[str] = None
    duration: Optional[str] = None
    medical_history: Optional[str] = None
    medication_history: Optional[str] = None
    allergy_history: Optional[str] = None    


class DepartmentRecommendRequest(BaseModel):
    """单独测试科室推荐模块请求"""
    symptoms: str
    age: Optional[int] = None
    gender: Optional[str] = None


class RiskDetectRequest(BaseModel):
    """单独测试危险信号模块请求"""
    symptoms: str
    duration: Optional[str] = None


class ReportAnalyzeRequest(BaseModel):
    """检查报告解释请求"""
    report_text: str
    age: Optional[int] = None
    gender: Optional[str] = None


# ============================================================
# Response Models
# ============================================================

class RiskResult(BaseModel):
    risk_level: str = Field(description="LOW/MEDIUM/HIGH")
    warnings: List[str] = Field(default_factory=list) 
    action: str = ""
    
class DepartmentResult(BaseModel):
    primary_department: str = ""
    alternative_departments: List[str] = Field(default_factory=list)
    reason: str = "" 


class HealthConsultResponse(BaseModel):
    """健康咨询完整响应"""
    summary: str
    possible_causes: List[str]
    risk_result: RiskResult
    department_result: DepartmentResult
    pre_visit_checklist: List[str]
    lifestyle_advice: List[str]
    references: List[str]
    disclaimer: str


# 用来健康检查的简单响应模型，保持接口稳定性
class HealthResponse(BaseModel):
    """健康检查响应模型"""
    message: str