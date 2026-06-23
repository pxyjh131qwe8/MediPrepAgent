from __future__ import annotations

import json 
from pathlib import Path
from typing import Any 

import jieba
from pydantic import BaseModel
from rank_bm25 import BM25Okapi

from app.config import settings
from langchain_core.documents import Document


class BM25ChunkRecord(BaseModel):
    """
    用于存储在BM25索引中的chunk信息。
    """
    chunk_id: str 
    content: str 
    metadata: dict[str, Any]  # 存储chunk的元数据，如document_id、chunk_index等


class BM25SearchResult(BaseModel):
    """
    BM25搜索结果的结构。
    """
    chunk_id: str 
    content: str 
    metadata: dict[str, Any]
    bm25_score: float  # BM25得分，用于衡量相关性    


def _chunks_path() -> Path:
    """
    获取存储BM25 chunks的JSON文件路径。
    """
    path = Path(settings.RAG_CHUNKS_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)  # 确保目录存在
    return path


def tokenize(text: str) -> list[str]:
    """
    中文BM25分词
    """
    return [
        token.strip().lower() 
        for token in jieba.lcut(text)
        if token.strip()  # 去除空白字符并转换为小写
    ]


    
def load_bm25_records() -> list[BM25ChunkRecord]: 
    path = _chunks_path() 
    
    if not path.exists():
        return []  # 如果文件不存在，返回空列表
    
    records: list[BM25ChunkRecord] = []
    
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue  # 跳过空行
            
            data = json.loads(line) 
            records.append(BM25ChunkRecord(**data))
    
    return records

def save_chunks_to_bm25_store(chunks: list[Document]) -> int:
    """
    将 chunks 写入 JSONL。

    这里做 chunk_id 去重，避免重复上传时无限追加。
    """
    path = _chunks_path() 
    
    existing_records = load_bm25_records() 
    existing_map = {
        item.chunk_id: item 
        for item in existing_records
    }
    
    for chunk in chunks:
        chunk_id = chunk.metadata.get("chunk_id") 
        
        if not chunk_id:
            continue  # 跳过没有chunk_id的chunk
        
        existing_map[chunk_id] = BM25ChunkRecord(
            chunk_id=chunk_id,
            content=chunk.page_content,
            metadata=dict(chunk.metadata or {}),
        )
        
    with path.open("w", encoding="utf-8") as f:
        for record in existing_map.values():
            f.write(
                json.dumps(
                    record.model_dump(),
                    ensure_ascii=False
                )
                + "\n"
            )    
    
    return len(chunks)         



def bm25_search(
    query: str,
    top_k: int = 10,
) -> list[BM25SearchResult]:
    """
    BM25关键词检索
    """
    records = load_bm25_records()
    
    if not records:
        return []
    
    corpus_tokens = [
        tokenize(record.content)
        for record in records
    ]
    
    bm25 = BM25Okapi(corpus_tokens)
    query_tokens = tokenize(query) 
    scores = bm25.get_scores(query_tokens)
    
    ranked_indexes = sorted(
        range(len(scores)),
        key=lambda i: scores[i],
        reverse=True
    )[:top_k]
    
    results: list[BM25SearchResult] = []
    
    for index in ranked_indexes: 
        record = records[index] 
        score = float(scores[index])
        
        if score <= 0:
            continue  # 跳过得分为0的结果
        
        results.append(
            BM25SearchResult(
                chunk_id=record.chunk_id,
                content=record.content,
                metadata=record.metadata,
                bm25_score=score
            )
        )
    
    return results    
