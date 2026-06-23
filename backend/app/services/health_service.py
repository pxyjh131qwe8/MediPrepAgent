# 后端主编排层
# 职责：接受用户请求 → 合并上下文 → 调用 Agent（Agent 自主检索 RAG）→ 保存上下文 → 返回结果

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import HealthConsultRequest, HealthConsultResponse
from app.services.health_context_service import HealthContextService
from app.agents.health_agent import HealthAgent, HealthAgentInput


class HealthService:
    """
    健康咨询主编排服务。
    RAG 检索已移入 Agent 内部（Function Calling），编排层不再预检索。
    """

    def __init__(self):
        self.health_agent = HealthAgent()
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

        # 3. 调用 Agent（Agent 内部通过 Function Calling 自主检索 RAG）
        agent_output = await self.health_agent.generate(
            HealthAgentInput(
                user_request=effective_request,
            ),
            thread_id=effective_request.thread_id,
        )

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
            disclaimer="本结果仅用于健康科普和就诊准备，不能替代医生诊断。如症状严重或持续加重，请及时线下就医。",
        )



