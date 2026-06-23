# 后端主编排层
# 它不直接写规则，也不直接写数据库细节，而是调用其他 service，把它们组合起来实现业务逻辑。
# 具体职责：接受用户请求 -> 调用risk_service -> 调用department_service -> 调用RAG检索 -> 调用health_agent -> 返回HealthConsultResult

# 先写无agent版本，后续再引入agent来优化流程

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import HealthConsultRequest, HealthConsultResponse
# from app.services.department_service import DepartmentService
# from app.services.risk_service import RiskService
from app.services.health_context_service import HealthContextService
from app.agents.health_agent import HealthAgent, HealthAgentInput
from app.agents.tools.rag_tool import MedicalRAGTool


class HealthService:
    """
    健康咨询主编排服务
    """

    def __init__(self):
        # self.risk_service = RiskService()
        # self.department_service = DepartmentService()
        self.health_agent = HealthAgent()
        self.context_service = HealthContextService()
        self.rag_tool = MedicalRAGTool()

    async def consult_health(
        self,
        request: HealthConsultRequest,
        db: AsyncSession,
    ) -> HealthConsultResponse:
        
        # 1. 默认使用本次request
        effective_request = request 
        
        # 2. 只有显示要求时，才会合并数据库上下文
        if request.use_saved_context:
            effective_request = await self.context_service.merge_with_saved_context(
                db=db,
                request=request
            )

        # 3. 规则服务永远基于effective_request
        # risk_result = self.risk_service.detect_risk(
        #     symptoms=effective_request.symptoms,
        #     duration=effective_request.duration,
        # )

        # department_result = self.department_service.recommend_department(
        #     symptoms=effective_request.symptoms,
        # )

        # 真实 RAG 检索
        rag_context, references = self.rag_tool.search_medical_knowledge(
            query=effective_request.symptoms,
            top_k=5,
        )

        agent_output = await self.health_agent.generate(
            HealthAgentInput(
                user_request=effective_request,
                # risk_result=risk_result,
                # department_result=department_result,
                rag_context=rag_context,
            ),
            thread_id=effective_request.thread_id,
        )

        # 4. 咨询成功后，保存本次明确病情
        # 注意：如果只是 use_saved_context=True 且 symptoms 是追问文本，
        # 前端应该传入真实 symptoms，或者调用单独的 chat 接口。
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
            references=references,
            disclaimer="本结果仅用于健康科普和就诊准备，不能替代医生诊断。如症状严重或持续加重，请及时线下就医。",
        )



