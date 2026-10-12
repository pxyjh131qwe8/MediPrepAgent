"""Health consultation application service."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import HealthConsultRequest, HealthConsultResponse
from app.agents.medical_team import MedicalTeam
from app.services.health_context_service import HealthContextService


class HealthService:
    """
    健康咨询主编排服务。
    Context persistence stays here; specialist collaboration lives in MedicalTeam.
    """

    def __init__(self):
        self.medical_team = MedicalTeam()
        # Kept as a compatibility alias for the existing lifespan integration.
        self.health_agent = self.medical_team.care_plan_agent
        self.context_service = HealthContextService()

    async def consult_health(
        self,
        request: HealthConsultRequest,
        db: AsyncSession,
    ) -> HealthConsultResponse:
        # 1. 默认使用本次 request
        effective_request = request

        # 2. 只有显式要求时，才合并数据库上下文
        if request.use_saved_context:
            effective_request = await self.context_service.merge_with_saved_context(
                db=db,
                request=request
            )

        # Triage and evidence retrieval run concurrently, followed by planning,
        # safety review, and a narrow tone pass.
        team_result = await self.medical_team.run(effective_request)
        agent_output = team_result.output

        # 4. 咨询成功后，保存本次病情
        await self.context_service.save_from_consult_request(
            db=db,
            request=effective_request
        )

        return HealthConsultResponse(
            summary=agent_output.summary,
            possible_causes=agent_output.possible_causes,
            risk_result=agent_output.risk_result,
            department_result=agent_output.department_result,
            pre_visit_checklist=agent_output.pre_visit_checklist,
            lifestyle_advice=agent_output.lifestyle_advice,
            references=agent_output.references,
            disclaimer="这份内容用于健康科普和就诊准备，不能代替医生面诊或诊断。身体感受如果明显加重，请及时线下就医。",
            evidence=team_result.evidence,
            follow_up_questions=team_result.follow_up_questions,
            agent_trace=team_result.trace,
            quality=team_result.quality,
        )



