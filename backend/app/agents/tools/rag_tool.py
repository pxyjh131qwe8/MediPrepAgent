# # app/agents/tools/rag_tool.py

# from app.rag.retriever import MedicalRetriever


# class MedicalRAGTool:
#     """
#     Agent 使用的医疗知识检索工具。
#     """

#     def __init__(self):
#         self.retriever = MedicalRetriever()

#     def search_medical_knowledge(
#         self,
#         query: str,
#         top_k: int = 5,
#     ) -> tuple[list[str], list[str]]:
#         """
#         返回：
#         contexts: 给 Agent 使用的上下文文本
#         references: 给前端展示的来源
#         """

#         results = self.retriever.retrieve(
#             query=query,
#             top_k=top_k,
#         )

#         contexts = []
#         references = []

#         for item in results:
#             contexts.append(
#                 f"【来源：{item.title}】\n{item.content}"
#             )

#             if item.title and item.title not in references:
#                 references.append(item.title)

#         return contexts, references

# app/agents/tools/rag_tool.py

from app.rag.hybrid_retriever import HybridMedicalRetriever


class MedicalRAGTool:
    """
    Agent 使用的医疗知识检索工具。

    当前版本：
    Chroma 向量检索 + BM25 关键词检索 + DashScope rerank
    """

    def __init__(self):
        self.retriever = HybridMedicalRetriever()

    def search_medical_knowledge(
        self,
        query: str,
        top_k: int = 5,
    ) -> tuple[list[str], list[str]]:

        results = self.retriever.retrieve(
            query=query,
            final_top_k=top_k,
        )

        contexts: list[str] = []
        references: list[str] = []

        for item in results:
            metadata = item.metadata or {}

            title = (
                metadata.get("title")
                or metadata.get("original_file_name")
                or metadata.get("file_name")
                or metadata.get("source")
                or "unknown"
            )

            page = metadata.get("page")

            ref = f"{title}"
            if page:
                ref += f":page-{page}"

            contexts.append(
                f"""【来源：{ref}】
【vector_score】：{item.vector_score:.4f}
【bm25_score】：{item.bm25_score:.4f}
【hybrid_score】：{item.hybrid_score:.4f}
【rerank_score】：{item.rerank_score:.4f}

{item.content}
"""
            )

            if ref not in references:
                references.append(ref)

        return contexts, references