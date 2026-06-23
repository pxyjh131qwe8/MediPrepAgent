from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.rag.hybrid_retriever import HybridMedicalRetriever
from app.services.knowledge_service import KnowledgeService


knowledge_router = APIRouter(
    prefix="/knowledge",
    tags=["knowledge"],
)

knowledge_service = KnowledgeService()
hybrid_retriever = HybridMedicalRetriever()


class KnowledgeSearchRequest(BaseModel):
    query: str
    top_k: int = 5


@knowledge_router.post("/upload")
async def upload_knowledge_file(
    file: UploadFile = File(..., description="上传单个知识库文件"),
    source_type: str = Form("uploaded_file"),
):
    try:
        return await knowledge_service.upload_and_ingest(
            file=file,
            source_type=source_type,
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"文件入库失败: {type(exc).__name__}: {exc}",
        )


@knowledge_router.post(
    "/upload/batch",
    description="批量上传知识库文件，支持 PDF / DOCX / TXT / MD",
)
async def upload_knowledge_files_batch(
    files: List[UploadFile],
    source_type: str = Form("uploaded_file"),
):
    if not files:
        raise HTTPException(
            status_code=400,
            detail="请至少上传一个文件",
        )

    return await knowledge_service.upload_many_and_ingest(
        files=files,
        source_type=source_type,
    )


@knowledge_router.post("/search")
async def search_knowledge(
    request: KnowledgeSearchRequest,
):
    results = hybrid_retriever.retrieve(
        query=request.query,
        final_top_k=request.top_k,
    )

    return {
        "query": request.query,
        "top_k": request.top_k,
        "results": [
            {
                "chunk_id": item.chunk_id,
                "content": item.content[:800],
                "metadata": item.metadata,
                "vector_score": item.vector_score,
                "bm25_score": item.bm25_score,
                "hybrid_score": item.hybrid_score,
                "rerank_score": item.rerank_score,
            }
            for item in results
        ],
    }