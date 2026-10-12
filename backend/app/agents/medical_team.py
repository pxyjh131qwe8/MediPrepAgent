"""Multi-agent collaboration pipeline for one consultation."""

from __future__ import annotations

import asyncio
from pydantic import BaseModel, Field

from app.agents.health_agent import HealthAgent, HealthAgentInput, HealthAgentOutput
from app.agents.specialist_agents import EvidenceAgent, SafetyReviewAgent, ToneAgent, TriageAgent
from app.models.schemas import AgentTraceStep, AnswerQuality, EvidenceItem, HealthConsultRequest


class MedicalTeamResult(BaseModel):
    output: HealthAgentOutput
    evidence: list[EvidenceItem] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    trace: list[AgentTraceStep] = Field(default_factory=list)
    quality: AnswerQuality


class MedicalTeam:
    """Coordinate specialist agents and expose a compact audit trail."""

    def __init__(self) -> None:
        self.triage_agent = TriageAgent()
        self.evidence_agent = EvidenceAgent()
        self.care_plan_agent = HealthAgent()
        self.safety_agent = SafetyReviewAgent()
        self.tone_agent = ToneAgent()

    async def setup(self) -> None:
        await self.care_plan_agent.setup_checkpointer()

    async def teardown(self) -> None:
        await self.care_plan_agent.teardown_checkpointer()

    async def run(self, request: HealthConsultRequest) -> MedicalTeamResult:
        triage, evidence = await asyncio.gather(
            self.triage_agent.run(request),
            self.evidence_agent.run(request),
        )

        trace = [
            AgentTraceStep(
                agent="triage",
                role="安全分诊",
                summary=self._triage_summary(triage.risk_level, triage.matched_signals, triage.negated_signals),
            ),
            AgentTraceStep(
                agent="evidence",
                role="证据检索",
                status="completed" if evidence else "limited",
                summary=(
                    f"找到 {len(evidence)} 条可追溯资料：{self._source_names(evidence)}。"
                    if evidence
                    else "没有找到直接相关资料，后续结果将采用保守表达。"
                ),
            ),
        ]

        output = await self.care_plan_agent.generate(
            HealthAgentInput(user_request=request, triage_result=triage, evidence=evidence),
            thread_id=request.thread_id,
        )
        trace.append(
            AgentTraceStep(
                agent="care_plan",
                role="就诊规划",
                summary=f"已整理首选科室、就诊准备和日常注意事项；首选 {output.department_result.primary_department}。",
            )
        )

        output, corrected, limitations = self.safety_agent.run(output, triage, evidence)
        trace.append(
            AgentTraceStep(
                agent="safety_review",
                role="医疗安全复核",
                status="corrected" if corrected else "completed",
                summary="已校验急症等级、诊断边界、用药边界和来源真实性。",
            )
        )

        output = self.tone_agent.run(output)
        trace.append(
            AgentTraceStep(
                agent="tone",
                role="温柔表达",
                summary="已在不改变医学含义的前提下，调整为自然、清楚的表达。",
            )
        )

        evidence_status = "grounded" if len(evidence) >= 2 else "limited" if evidence else "unavailable"
        if len(evidence) == 1:
            limitations.append("当前只检索到一个直接相关来源，结论仍需结合线下医生评估。")

        return MedicalTeamResult(
            output=output,
            evidence=evidence,
            follow_up_questions=self._follow_up_questions(request),
            trace=trace,
            quality=AnswerQuality(
                evidence_status=evidence_status,
                safety_reviewed=True,
                limitations=list(dict.fromkeys(limitations)),
            ),
        )

    @staticmethod
    def _source_names(evidence: list[EvidenceItem]) -> str:
        return "、".join(list(dict.fromkeys(item.source for item in evidence)))

    @staticmethod
    def _triage_summary(level: str, matched: list[str], negated: list[str]) -> str:
        parts = [f"规则分诊为 {level}"]
        if matched:
            parts.append(f"识别到：{'、'.join(matched)}")
        if negated:
            parts.append(f"已正确排除否认症状：{'、'.join(negated)}")
        return "；".join(parts) + "。"

    @staticmethod
    def _follow_up_questions(request: HealthConsultRequest) -> list[str]:
        questions: list[str] = []
        if not request.duration:
            questions.append("这种不舒服大约从什么时候开始？是持续存在，还是一阵一阵出现？")
        if request.age is None:
            questions.append("方便补充一下年龄吗？不同年龄段需要关注的情况会有些不同。")

        text = request.symptoms
        if not any(word in text for word in ("程度", "分", "轻", "重", "影响")):
            questions.append("如果用 0 到 10 分表示不适程度，现在大约是几分？有没有影响睡眠或日常活动？")
        if not any(word in text for word in ("加重", "缓解", "诱因", "运动后", "饭后")):
            questions.append("什么情况下会加重或缓解？最近有没有发现比较明确的诱因？")
        return questions[:3]
