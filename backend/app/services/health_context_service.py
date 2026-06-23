from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db_models import HealthSessionContext
from app.models.schemas import HealthConsultRequest, HealthContextUpdateRequest


class HealthContextService:
    """
    健康上下文服务
    ==============
    用于保存和读取同一个 thread_id 下的结构化病情信息。
    """
    
    # 按照 thread_id 查询
    async def get_context(
        self, 
        db: AsyncSession,
        thread_id: str
    ) -> HealthSessionContext | None:
        result = await db.execute(
            select(HealthSessionContext).where(
                HealthSessionContext.thread_id == thread_id
            )
        )
        return result.scalar_one_or_none()
    
    # 更新内容
    async def upsert_context(
        self,
        db: AsyncSession,
        request: HealthContextUpdateRequest,
    ) -> HealthSessionContext:
        context = await self.get_context(db, request.thread_id)

        if context is None:
            context = HealthSessionContext(thread_id=request.thread_id)
            db.add(context)

        if request.age is not None:
            context.age = request.age

        if request.gender is not None:
            context.gender = request.gender

        if request.latest_symptoms is not None:
            context.latest_symptoms = request.latest_symptoms

        if request.duration is not None:
            context.duration = request.duration

        if request.medical_history is not None:
            context.medical_history = request.medical_history

        if request.medication_history is not None:
            context.medication_history = request.medication_history

        if request.allergy_history is not None:
            context.allergy_history = request.allergy_history

        await db.commit()
        await db.refresh(context)

        return context
    
    # 新增保存
    async def save_from_consult_request(
        self, 
        db: AsyncSession,
        request: HealthConsultRequest
    ) -> None:
        """
        咨询完成后，把本次明确输入的病情保存下来
        """ 
        thread_id = request.thread_id 
        
        update_request = HealthContextUpdateRequest(
            thread_id = thread_id,
            age = request.age,
            gender = request.gender,
            latest_symptoms = request.symptoms,
            duration = request.duration,
            medical_history = request.medical_history,
            medication_history = request.medication_history,
            allergy_history = request.allergy_history
        )
        
        await self.upsert_context(db, update_request)
    
    # 新增一个方法，合并历史上下文到本次输入中
    async def merge_with_saved_context(
        self,
        db: AsyncSession,
        request: HealthConsultRequest
    ) -> HealthConsultRequest:
        """
        只有 request.use_saved_context=True 时才调用。
        """  
        thread_id = request.thread_id
        
        context = await self.get_context(db, thread_id) 
        
        if context is None:
            return request
        
        # 为什么or 操作？因为如果本次输入里没有提供某个字段，就用历史上下文里的值；如果本次输入里提供了，就用本次输入的值。
        return HealthConsultRequest(
            thread_id=thread_id,
            age=request.age or context.age,
            gender=request.gender or context.gender,
            symptoms=request.symptoms or context.latest_symptoms or "",
            duration=request.duration or context.duration,
            medical_history=request.medical_history or context.medical_history,
            medication_history=request.medication_history or context.medication_history,
            allergy_history=request.allergy_history or context.allergy_history,
            goal=request.goal,
            use_saved_context=request.use_saved_context,
        )