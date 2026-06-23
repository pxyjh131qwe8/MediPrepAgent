from __future__ import annotations

from pydantic import BaseModel

from app.config import settings
from app.rag.bm25_store import bm25_search
from app.rag.dashscope_reranker import DashScopeReranker, RerankCandidate
from app.rag.vector_db import vector_search


class HybridRetrievedContext(BaseModel):
    chunk_id: str
    content: str
    metadata: dict
    vector_score: float = 0.0
    bm25_score: float = 0.0
    hybrid_score: float = 0.0
    rerank_score: float = 0.0



def _normalize_scores(score_map: dict[str, float]) -> dict[str, float]:
    """
    将分数归一化到0-1
    BM25分数没有固定范围，需要归一化
    """ 
    if not score_map:
        return {} 
    
    max_score = max(score_map.values())
    if max_score <= 0:
        return {
            key: 0.0
            for key in score_map
        }
    
    return {
        key: value / max_score
        for key, value in score_map.items()
    }    


def _chroma_distance_to_similarity(distance: float) -> float:
    """
    Chroma 返回的一般是 distance。
    distance 越小越相似。

    转换成 similarity：
    similarity = 1 / (1 + distance)
    """
    return 1.0 / (1.0 + max(distance, 0.0)) 
        

class HybridMedicalRetriever:
    """
    混合检索器：

    1. Chroma 向量召回
    2. BM25 关键词召回
    3. 分数融合
    4. DashScope rerank
    """
    def __init__(self):
        self.reranker = DashScopeReranker() 
    
    def retrieve(
        self,
        query: str,
        final_top_k: int | None = None,
    ) -> list[HybridRetrievedContext]:

        final_top_k = final_top_k or settings.RAG_FINAL_TOP_K

        vector_results = vector_search(
            query=query,
            top_k=settings.RAG_VECTOR_TOP_K,
        )

        bm25_results = bm25_search(
            query=query,
            top_k=settings.RAG_BM25_TOP_K,
        )

        candidate_map: dict[str, RerankCandidate] = {}

        raw_vector_scores: dict[str, float] = {}
        raw_bm25_scores: dict[str, float] = {}

        # 1. 收集 Chroma 向量召回结果
        for doc, distance in vector_results:
            metadata = dict(doc.metadata or {})

            chunk_id = metadata.get("chunk_id")

            if chunk_id is None or chunk_id == "":
                chunk_id = f"vector-{abs(hash(doc.page_content))}"
            else:
                chunk_id = str(chunk_id)

            metadata["chunk_id"] = chunk_id

            similarity = _chroma_distance_to_similarity(float(distance))

            raw_vector_scores[chunk_id] = similarity

            candidate_map[chunk_id] = RerankCandidate(
                chunk_id=chunk_id,
                content=doc.page_content,
                metadata=metadata,
                vector_score=similarity,
            )

        # 2. 收集 BM25 关键词召回结果
        for item in bm25_results:
            chunk_id = str(item.chunk_id)

            raw_bm25_scores[chunk_id] = item.bm25_score

            metadata = dict(item.metadata or {})
            metadata["chunk_id"] = chunk_id

            candidate = candidate_map.get(chunk_id)

            if candidate is None:
                candidate_map[chunk_id] = RerankCandidate(
                    chunk_id=chunk_id,
                    content=item.content,
                    metadata=metadata,
                    bm25_score=item.bm25_score,
                )
            else:
                candidate.bm25_score = item.bm25_score
                candidate.metadata.update(metadata)

        # 3. 归一化分数
        normalized_vector = _normalize_scores(raw_vector_scores)
        normalized_bm25 = _normalize_scores(raw_bm25_scores)

        for chunk_id, candidate in candidate_map.items():
            v_score = normalized_vector.get(chunk_id, 0.0)
            b_score = normalized_bm25.get(chunk_id, 0.0)

            candidate.vector_score = v_score
            candidate.bm25_score = b_score
            candidate.hybrid_score = (
                settings.RAG_VECTOR_WEIGHT * v_score
                + settings.RAG_BM25_WEIGHT * b_score
            )

        # 4. 先按 hybrid_score 截取候选
        candidates = sorted(
            candidate_map.values(),
            key=lambda x: x.hybrid_score,
            reverse=True,
        )[: max(final_top_k * 4, 20)]

        # 5. DashScope rerank
        reranked = self.reranker.rerank(
            query=query,
            candidates=candidates,
            top_n=final_top_k,
        )

        return [
            HybridRetrievedContext(
                chunk_id=item.chunk_id,
                content=item.content,
                metadata=item.metadata,
                vector_score=item.vector_score,
                bm25_score=item.bm25_score,
                hybrid_score=item.hybrid_score,
                rerank_score=item.rerank_score,
            )
            for item in reranked
        ]
        






