from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.config import settings
from app.models.schemas import (
    HealthConsultRequest,
    RiskResult,
    DepartmentResult,
)


# class RiskResult(BaseModel):
#     risk_level: str = Field(description="LOW/MEDIUM/HIGH")
#     warnings: List[str] = Field(default_factory=list) 
#     action: str = ""
    
# class DepartmentResult(BaseModel):
#     primary_department: str = ""
#     alternative_departments: List[str] = Field(default_factory=list)
#     reason: str = ""     



class HealthAgentOutput(BaseModel):
    summary: str
    possible_causes: List[str] = Field(default_factory=list)
    risk_result: RiskResult
    department_result: DepartmentResult
    pre_visit_checklist: List[str] = Field(default_factory=list)
    lifestyle_advice: List[str] = Field(default_factory=list)

class HealthAgentInput(BaseModel):
    user_request: HealthConsultRequest
    # risk_result: RiskResult
    # department_result: DepartmentResult
    rag_context: List[str] = Field(default_factory=list)


@tool
def medical_safety_rule_tool() -> str:
    """返回医疗健康agent的安全边界""" 
    return (
        "你不能做疾病确诊，不能替代医生，不能推荐处方药，"
        "不能给出具体治疗方案。你只能做健康科普、风险提醒、"
        "科室建议解释和就诊准备。"
    )


class HealthAgent:
    """
    基于 LangChain create_agent 的健康咨询 Agent。

    特点：
    1. 使用 create_agent 构建正式 Agent
    2. 使用 AsyncPostgresSaver（PostgreSQL）持久化对话历史，服务重启不丢失
    3. 使用 SummarizationMiddleware 做长对话摘要
    4. 使用 thread_id 区分不同用户/会话
    5. 输出结构化 JSON

    Checkpointer 初始化：
    - 构造时先用 InMemorySaver 做降级兜底
    - lifespan 中调用 setup_checkpointer() 升级为 PostgreSQL
    """
    SYSTEM_PROMPT = """
你是 MediPrepAgent，一个谨慎、专业的智能就诊准备助手。

你的任务：
1. 根据用户描述进行健康科普。
2. 根据症状推荐可能适合咨询的科室。
3. 根据用户描述判断风险等级 LOW / MEDIUM / HIGH。
4. 结合 RAG 检索资料生成就诊准备建议。

重要安全规则：
1. 你不能做疾病确诊。
2. 你不能替代医生诊疗。
3. 你不能推荐处方药、剂量或具体治疗方案。
4. 你只能做健康科普、风险提示、科室导航和就诊准备。
5. 如果用户明确否认某症状，例如“没有胸痛”“无呼吸困难”“否认肢体无力”，不得把这些否认的症状当作阳性高危信号。
6. 只有用户明确描述存在高危症状时，才可以判断为 HIGH。
7. 如果用户描述的是头痛、失眠、压力大，但明确没有胸痛、呼吸困难、肢体无力、意识模糊，一般不应判断为 HIGH。
8. 如果风险不确定，优先给出 MEDIUM 或 LOW，并建议线下医生评估。
9. 输出必须是合法 JSON，不要输出 Markdown，不要输出代码块。

风险等级参考：
- HIGH：明确存在胸痛伴呼吸困难/大汗、意识模糊、昏迷、抽搐、突发肢体无力、说话不清、大量出血、呕血黑便伴明显不适等急症信号。
- MEDIUM：症状持续较久、反复发作、明显影响生活，但暂无明确急症信号。
- LOW：轻度、短期、暂无明显高危信号的症状。

你必须输出如下 JSON：
{
  "summary": "...",
  "possible_causes": ["...", "..."],
  "risk_result": {
    "risk_level": "LOW/MEDIUM/HIGH",
    "warnings": ["...", "..."],
    "action": "..."
  },
  "department_result": {
    "primary_department": "...",
    "alternative_departments": ["...", "..."],
    "reason": "..."
  },
  "pre_visit_checklist": ["...", "..."],
  "lifestyle_advice": ["...", "..."]
}
"""

    def __init__(self):
        # 先用 InMemorySaver 做降级兜底，lifespan 中会调用 setup_checkpointer()
        # 升级为 AsyncPostgresSaver（PostgreSQL 持久化）
        self.checkpointer: InMemorySaver | AsyncPostgresSaver = InMemorySaver()

        self.middleware = SummarizationMiddleware(
            model=settings.LLM_MODEL,
            trigger=("messages", 6),
            keep=("messages", 2),
        )

        self.agent = create_agent(
            model=settings.LLM_MODEL,
            tools=[medical_safety_rule_tool],
            system_prompt=self.SYSTEM_PROMPT,
            checkpointer=self.checkpointer,
            middleware=[self.middleware],
        )

    async def setup_checkpointer(self) -> None:
        """
        由 FastAPI lifespan 调用，将 checkpointer 升级为 PostgreSQL 持久化。

        调用时机：应用启动后、接收请求前。
        失败时保留 InMemorySaver 降级运行，不会阻断服务启动。
        """
        try:
            # from_conn_string 返回异步上下文管理器，需要进入后才拿到实例
            self._pg_context = AsyncPostgresSaver.from_conn_string(
                settings.CHECKPOINT_DATABASE_URL
            )
            pg_checkpointer = await self._pg_context.__aenter__()
            await pg_checkpointer.setup()
            self.checkpointer = pg_checkpointer
            # 用 PostgreSQL checkpointer 重建 agent
            self.agent = create_agent(
                model=settings.LLM_MODEL,
                tools=[medical_safety_rule_tool],
                system_prompt=self.SYSTEM_PROMPT,
                checkpointer=self.checkpointer,
                middleware=[self.middleware],
            )
            print("[HealthAgent] ✅ Checkpointer 已升级为 PostgreSQL 持久化")
        except Exception as exc:
            print(f"[HealthAgent] ⚠️ PostgreSQL checkpointer 初始化失败，降级为 InMemorySaver: {exc}")
            print("[HealthAgent] ⚠️ 对话历史将在服务重启后丢失")

    async def teardown_checkpointer(self) -> None:
        """
        由 FastAPI lifespan 关闭阶段调用，释放 PostgreSQL 连接池。
        """
        ctx = getattr(self, "_pg_context", None)
        if ctx is not None:
            try:
                await ctx.__aexit__(None, None, None)
                print("[HealthAgent] ✅ PostgreSQL checkpointer 连接池已释放")
            except Exception as exc:
                print(f"[HealthAgent] ⚠️ 关闭 checkpointer 时出错: {exc}")
    
    async def generate(self,
                       agent_input: HealthAgentInput,
                       thread_id: str | None = None
    ) -> HealthAgentOutput:  
        """
        调用 LangChain Agent 生成健康建议。
        """
        final_thread_id = thread_id or agent_input.user_request.thread_id or "default-health-thread"

        config: RunnableConfig = {
            "configurable": {
                "thread_id": final_thread_id
            }
        }
        
        user_prompt = self._build_user_prompt(agent_input)
        
        try: 
            # 调用 Agent
            result = await self.agent.ainvoke(
                {
                    "messages": [
                        HumanMessage(content=user_prompt)
                    ]
                },
                config=config
            )
            # 解析输出
            raw_text = self._extract_final_text(result)
            return self._parse_json_output(raw_text, agent_input)
        except Exception as exc:
            print(f"[HealthAgent] Agent 调用失败，使用降级输出: {type(exc).__name__}: {exc}")
            return self._fallback_output(agent_input)
    
    # 构建用户提示语，包含所有输入信息和 RAG 资料
    def _build_user_prompt(self, inp: HealthAgentInput) -> str:
        req = inp.user_request
        # risk = inp.risk_result
        # dept = inp.department_result

        rag_text = "\n".join(inp.rag_context) if inp.rag_context else "暂无 RAG 检索资料。"

        return f"""
请根据以下信息生成健康科普和就诊准备建议。

【用户基本信息】
年龄：{req.age or "未知"}
性别：{req.gender or "未知"}

【用户症状】
{req.symptoms}

【持续时间】
{req.duration or "未提供"}

【既往病史】
{req.medical_history or "未提供"}

【用药史】
{req.medication_history or "未提供"}

【过敏史】
{req.allergy_history or "未提供"}

【用户目标】
{req.goal or "未提供"}


【RAG 参考资料】
{rag_text}


请特别注意：
1. 用户明确否认的症状，不能作为阳性症状。
2. 不要因为文本中出现“没有胸痛”“无呼吸困难”就判断用户有胸痛或呼吸困难。
3. 只能做就诊准备和健康科普，不能诊断。
4. 科室推荐要说明理由。
5. 输出合法 JSON。
""" 
    
    def _extract_final_text(self, result) -> str:
        """
        从 create_agent 返回结果中提取最后一条 AI 消息。
        """
        messages = result.get("messages", [])
        if not messages:
            return ""

        last_message = messages[-1]
        content = getattr(last_message, "content", "")

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            return "".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )

        return str(content)

    def _parse_json_output(
        self,
        raw_text: str,
        agent_input: HealthAgentInput,
    ) -> HealthAgentOutput:
        """
        解析 Agent JSON 输出。
        """
        text = raw_text.strip()

        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1 and end > start:
            text = text[start:end + 1]

        try:
            data = json.loads(text)

            risk_data = data.get("risk_result") or {}
            department_data = data.get("department_result") or {}

            return HealthAgentOutput(
                summary=data.get("summary", ""),
                possible_causes=data.get("possible_causes", []),
                risk_result=RiskResult(
                    risk_level=risk_data.get("risk_level", "MEDIUM"),
                    warnings=risk_data.get("warnings", []),
                    action=risk_data.get("action", "建议根据症状持续情况，线下就医评估。"),
                ),
                department_result=DepartmentResult(
                    primary_department=department_data.get("primary_department", "人工导诊台"),
                    alternative_departments=department_data.get("alternative_departments", []),
                    reason=department_data.get("reason", "根据用户描述，建议先进行线下医学评估。"),
                ),
                pre_visit_checklist=data.get("pre_visit_checklist", []),
                lifestyle_advice=data.get("lifestyle_advice", []),
            )

        except Exception as exc:
            print("[HealthAgent] JSON 解析失败，使用降级输出")
            print(f"[HealthAgent] 错误类型: {type(exc).__name__}")
            print(f"[HealthAgent] 错误详情: {exc}")
            print(f"[HealthAgent] 清洗后文本: {text[:1000]}")
            print(f"[HealthAgent] 原始输出: {raw_text[:1000]}")
            return self._fallback_output(agent_input)

    def _fallback_output(
        self,
        inp: HealthAgentInput,
    ) -> HealthAgentOutput:
        symptoms = inp.user_request.symptoms

        return HealthAgentOutput(
            summary=(
                f"根据你描述的症状「{symptoms}」，系统已完成初步就诊准备整理。"
                "目前无法替代医生判断，建议结合线下医生问诊和检查进一步评估。"
            ),
            risk_result=RiskResult(
                risk_level="MEDIUM",
                warnings=[
                    "当前无法由系统做出诊断判断。",
                    "如果症状持续加重，或出现胸痛、呼吸困难、意识异常、肢体无力等新发危险信号，请及时线下就医。",
                ],
                action="建议根据症状持续时间和影响程度，预约相关科室或全科医学科进行评估。",
            ),
            department_result=DepartmentResult(
                primary_department="人工导诊台",
                alternative_departments=["神经内科", "睡眠医学科", "精神心理科"],
                reason="根据用户描述相关表现，可先由人工导诊台评估，再根据医生建议转诊相关专科。",
            ),
            possible_causes=[
                "症状可能与多种因素相关，需要医生结合问诊、体格检查和必要检查综合判断。",
                "当前建议仅作为健康科普和就诊准备，不能作为诊断依据。",
            ],
            pre_visit_checklist=[
                "记录症状出现时间、持续时间、加重或缓解因素。",
                "记录是否伴随发热、胸痛、呼吸困难、意识异常等症状。",
                "携带既往检查报告、用药记录和过敏史。",
            ],
            lifestyle_advice=[
                "保持规律作息，避免过度劳累。",
                "不要自行长期用药或随意加减药。",
                "如果症状加重或出现新的危险信号，请及时线下就医。",
            ],
        )       
        
        


