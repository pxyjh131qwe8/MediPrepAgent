"""
LangChain RAG 检索工具 — Agent 自主调用，实现真正的 Function Calling。
"""

from langchain_core.tools import tool

from app.rag.hybrid_retriever import HybridMedicalRetriever

# 模块级单例，避免每次 tool 调用都重建 retriever
_retriever = HybridMedicalRetriever()


def _format_context(item) -> str:
    """将单条检索结果格式化为 LLM 可读文本"""
    metadata = item.metadata or {}

    title = (
        metadata.get("title")
        or metadata.get("original_file_name")
        or metadata.get("file_name")
        or metadata.get("source")
        or "未知来源"
    )
    page = metadata.get("page")
    ref = f"{title}"
    if page:
        ref += f" 第{page}页"

    return (
        f"【来源：{ref}】\n"
        f"相关性得分：{item.hybrid_score:.4f}\n"
        f"{item.content}"
    )


@tool
def rag_search(query: str) -> str:
    """搜索医学知识库。

    当你需要查找与用户症状相关的医学知识、科室信息、就诊建议时，调用此工具。
    传入一个中文查询词（如症状名称或医学问题），返回最相关的医学资料。

    参数：
        query: 中文检索词，例如 "头痛的原因和就诊建议"、"胸痛需要挂什么科"
    返回：
        格式化的医学参考资料文本，含来源标注。
    """
    results = _retriever.retrieve(query=query, final_top_k=5)
    if not results:
        return "未找到相关医学资料，请基于你的医学常识为用户提供谨慎建议。"

    return "\n\n---\n\n".join(
        _format_context(item) for item in results
    )
