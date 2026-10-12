"""Pydantic request and response models for MediPrepAgent."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================
# Request Models
# ============================================================

class HealthConsultRequest(BaseModel):
    """用户提交健康咨询请求"""
    age: Optional[int] = Field(default=None, ge=0, le=120)
    gender: Optional[str] = Field(default=None, max_length=30)
    symptoms: str = Field(min_length=2, max_length=2000)
    duration: Optional[str] = Field(default=None, max_length=100)
    medical_history: Optional[str] = Field(default=None, max_length=1000)
    medication_history: Optional[str] = Field(default=None, max_length=1000)
    allergy_history: Optional[str] = Field(default=None, max_length=1000)
    goal: Optional[str] = Field(default=None, max_length=500)
    
    # 新增
    thread_id: str = Field(default="default_thread_id", min_length=1, max_length=100)
    # 显式控制是否合并历史上下文
    use_saved_context: bool = False

    @field_validator("symptoms")
    @classmethod
    def symptoms_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("请描述目前最困扰你的症状")
        return value
    
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
    risk_level: Literal["LOW", "MEDIUM", "HIGH"] = Field(description="LOW/MEDIUM/HIGH")
    warnings: List[str] = Field(default_factory=list) 
    action: str = ""
    matched_signals: List[str] = Field(default_factory=list)
    negated_signals: List[str] = Field(default_factory=list)
    
class DepartmentResult(BaseModel):
    primary_department: str = ""
    alternative_departments: List[str] = Field(default_factory=list)
    reason: str = "" 


class EvidenceItem(BaseModel):
    """A source excerpt actually used by the recommendation."""

    source: str
    title: str = "医学资料"
    excerpt: str
    relevance: float = Field(default=0.0, ge=0.0, le=1.0)


class AgentTraceStep(BaseModel):
    """Auditable summary of one specialist agent's contribution."""

    agent: str
    role: str
    status: Literal["completed", "limited", "corrected"] = "completed"
    summary: str


class AnswerQuality(BaseModel):
    evidence_status: Literal["grounded", "limited", "unavailable"] = "unavailable"
    safety_reviewed: bool = True
    limitations: List[str] = Field(default_factory=list)


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
    evidence: List[EvidenceItem] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)
    agent_trace: List[AgentTraceStep] = Field(default_factory=list)
    quality: AnswerQuality = Field(default_factory=AnswerQuality)


# 用来健康检查的简单响应模型，保持接口稳定性
class HealthResponse(BaseModel):
    """健康检查响应模型"""
    message: str
