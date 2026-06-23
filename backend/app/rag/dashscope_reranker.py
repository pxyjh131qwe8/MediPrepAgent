from __future__ import annotations

import requests
from pydantic import BaseModel

from app.config import settings


class RerankCandidate(BaseModel):
    chunk_id: str
    content: str
    metadata: dict
    vector_score: float = 0.0
    bm25_score: float = 0.0
    hybrid_score: float = 0.0
    rerank_score: float = 0.0


class DashScopeReranker:
    """
    DashScope 文本重排序。

    默认使用 qwen3-rerank。
    如果未配置 DASHSCOPE_API_KEY 或调用失败，则回退到 hybrid_score 排序。
    """
    
    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY
        self.model = settings.DASHSCOPE_RERANK_MODEL 
        self.enabled = settings.DASHSCOPE_RERANK_ENABLED 
        
        self.endpoint = "https://dashscope.aliyuncs.com/compatible-api/v1/reranks"
        
    def rerank(
        self, 
        query: str, 
        candidates: list[RerankCandidate],
        top_n: int = 5 
    ) -> list[RerankCandidate]:    
        
        if not candidates:
            return []
        
        if not self.enabled or not self.api_key:
            return sorted(
                candidates,
                key=lambda x: x.hybrid_score,
                reverse=True
            )[:top_n]
        
        documents = [
            item.content[:3000]
            for item in candidates
        ] 
        
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": min(top_n, len(documents)),
            "instruct": "Given a medical consultation query, retrieve relevant passages that help answer the query safely.",
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=30,
            )

            response.raise_for_status()

            data = response.json()

            results = data.get("results", [])

            reranked: list[RerankCandidate] = []

            for item in results:
                original_index = item.get("index")
                score = float(item.get("relevance_score", 0.0))

                if original_index is None:
                    continue

                candidate = candidates[original_index]
                candidate.rerank_score = score
                reranked.append(candidate)

            if not reranked:
                return sorted(
                    candidates,
                    key=lambda x: x.hybrid_score,
                    reverse=True,
                )[:top_n]

            return reranked[:top_n]

        except Exception as exc:
            print(f"[DashScopeReranker] rerank failed: {type(exc).__name__}: {exc}")

            return sorted(
                candidates,
                key=lambda x: x.hybrid_score,
                reverse=True,
            )[:top_n]   
        