"""Care-plan specialist backed by an OpenAI-compatible chat endpoint.

Urgency is decided before this agent runs and is never delegated to the model.
The model's job is to turn verified evidence into a useful visit-preparation
plan. Keeping that boundary explicit makes failures easier to audit.
"""

from __future__ import annotations

import json
from typing import List

import httpx
from pydantic import BaseModel, Field

from app.config import settings
from app.models.schemas import (
    DepartmentResult,
    EvidenceItem,
    HealthConsultRequest,
    RiskResult,
)
from app.services.department_service import DepartmentService


class HealthAgentOutput(BaseModel):
    summary: str
    possible_causes: List[str] = Field(default_factory=list)
    risk_result: RiskResult
    department_result: DepartmentResult
    pre_visit_checklist: List[str] = Field(default_factory=list)
    lifestyle_advice: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)


class HealthAgentInput(BaseModel):
    user_request: HealthConsultRequest
    triage_result: RiskResult
    evidence: List[EvidenceItem] = Field(default_factory=list)


class HealthAgent:
    """Synthesize a grounded, gentle visit-preparation plan."""

    SYSTEM_PROMPT = """
你是 MediPrepAgent 医疗协作组里的就诊规划专员。你的工作不是诊断，而是帮助用户更从容地准备就医。

硬性边界：
1. 不确诊，不暗示已经确诊，不替代医生，不开处方，不给药物剂量或具体治疗方案。
2. 只使用输入中给出的用户事实和医学资料。资料没有覆盖的内容，要明确说“仅凭目前信息无法判断”。
3. 可能相关因素只能用“可能与……有关”“医生通常会结合……排查”等非诊断表达。
4. 上游分诊结果是确定性安全结论，不得降低风险等级，也不得删除其行动建议。
5. 用户明确否认的症状绝不能当作阳性症状。
6. 表达像一位认真、温和的医护人员：句子自然、具体，不说“作为AI”“根据大数据”“亲亲”等话。
7. 不渲染焦虑。高风险时直接、清楚地说明下一步。
8. 只输出合法 JSON，不输出 Markdown 或额外解释。

输出结构：
{
  "summary": "两三句自然、温和的概括",
  "possible_causes": ["可能相关的因素；资料不足时可为空"],
  "department_result": {
    "primary_department": "首选科室",
    "alternative_departments": ["备选科室"],
    "reason": "与症状和资料对应的理由"
  },
  "pre_visit_checklist": ["具体可执行的准备事项"],
  "lifestyle_advice": ["低风险、保守的日常建议"]
}
"""

    def __init__(self) -> None:
        self.department_service = DepartmentService()

    async def setup_checkpointer(self) -> None:
        """Compatibility no-op; context is stored by HealthContextService."""

    async def teardown_checkpointer(self) -> None:
        """Compatibility no-op."""

    async def generate(
        self,
        agent_input: HealthAgentInput,
        thread_id: str | None = None,
    ) -> HealthAgentOutput:
        if not settings.LLM_API_KEY:
            return self._fallback_output(agent_input)

        try:
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
                    json={
                        "model": settings.LLM_MODEL,
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": self.SYSTEM_PROMPT},
                            {"role": "user", "content": self._build_user_prompt(agent_input)},
                        ],
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
            return self._parse_json_output(content, agent_input)
        except Exception as exc:
            print(f"[CarePlanAgent] 模型调用失败，使用保守降级结果: {type(exc).__name__}: {exc}")
            return self._fallback_output(agent_input)

    def _build_user_prompt(self, inp: HealthAgentInput) -> str:
        req = inp.user_request
        return json.dumps(
            {
                "用户信息": {
                    "年龄": req.age,
                    "性别": req.gender,
                    "症状": req.symptoms,
                    "持续时间": req.duration,
                    "既往病史": req.medical_history,
                    "用药史": req.medication_history,
                    "过敏史": req.allergy_history,
                    "这次最想解决": req.goal,
                },
                "确定性分诊结果_不得降低": inp.triage_result.model_dump(),
                "已检索医学资料_只可引用这些事实": [item.model_dump() for item in inp.evidence],
            },
            ensure_ascii=False,
        )

    def _parse_json_output(self, raw_text: str, inp: HealthAgentInput) -> HealthAgentOutput:
        text = raw_text.strip()
        if text.startswith("```"):
            text = "\n".join(text.splitlines()[1:-1]).strip()
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]

        try:
            data = json.loads(text)
            department = data.get("department_result") or {}
            references = list(dict.fromkeys(item.source for item in inp.evidence))
            return HealthAgentOutput(
                summary=str(data.get("summary") or "").strip(),
                possible_causes=[str(item) for item in data.get("possible_causes", [])][:6],
                risk_result=inp.triage_result,
                department_result=DepartmentResult(
                    primary_department=str(department.get("primary_department") or "全科医学科"),
                    alternative_departments=[str(item) for item in department.get("alternative_departments", [])][:4],
                    reason=str(department.get("reason") or "可先由医生结合问诊和检查判断下一步。"),
                ),
                pre_visit_checklist=[str(item) for item in data.get("pre_visit_checklist", [])][:8],
                lifestyle_advice=[str(item) for item in data.get("lifestyle_advice", [])][:6],
                references=references,
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return self._fallback_output(inp)

    def _fallback_output(self, inp: HealthAgentInput) -> HealthAgentOutput:
        req = inp.user_request
        department = self.department_service.recommend_department(req.symptoms)
        if inp.triage_result.risk_level == "HIGH":
            department = DepartmentResult(
                primary_department="急诊科",
                alternative_departments=[],
                reason="目前描述中有需要尽快排查的危险信号，先由急诊评估更稳妥。",
            )

        evidence_sources = list(dict.fromkeys(item.source for item in inp.evidence))
        possible_factors = (
            ["仅凭目前描述还不能判断具体原因，需要医生结合问诊、体格检查和必要检查进一步排查。"]
            if not inp.evidence
            else ["目前表现可能与多种常见因素有关，具体原因仍需医生结合面诊判断。"]
        )
        return HealthAgentOutput(
            summary=(
                f"我记下了你提到的“{req.symptoms}”。先别急着给它下结论，"
                "更重要的是确认是否有需要尽快处理的信号，并把就诊信息准备完整。"
            ),
            possible_causes=possible_factors,
            risk_result=inp.triage_result,
            department_result=department,
            pre_visit_checklist=[
                "记录症状从什么时候开始、每次持续多久，以及最近是否变重。",
                "记下可能的诱因、缓解方式和同时出现的其他不适。",
                "带上既往检查报告，并整理正在使用的药物和过敏信息。",
                "把最想问医生的两三个问题提前写下来。",
            ],
            lifestyle_advice=[
                "在明确原因前，先保证休息和正常饮水，避免勉强工作或剧烈运动。",
                "不要因为这份建议自行开始、停用或调整处方药。",
            ],
            references=evidence_sources,
        )
