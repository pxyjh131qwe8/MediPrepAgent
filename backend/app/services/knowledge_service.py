from __future__ import annotations

import shutil 
import uuid 
from pathlib import Path
from typing import Any

from fastapi import UploadFile 
from langchain_core.documents import Document 

from app.config import settings
from app.rag.bm25_store import save_chunks_to_bm25_store 
from app.rag.chunker import chunk_documents 
from app.rag.document_loader import SUPPORTED_EXTENSIONS, load_document_file 
from app.rag.vector_db import add_documents_to_vector_store 


class KnowledgeService:
    """
    本地知识库服务。

    职责：
    1. 保存用户上传文件
    2. 加载 PDF / DOCX / TXT / MD
    3. 切片
    4. 写入 Chroma
    5. 写入 BM25 JSONL 索引
    """
    
    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DOCS_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True) 
    
    async def upload_and_ingest(
        self, 
        file: UploadFile,
        source_type: str = "uploaded_file"
    ) -> dict: 
        """
        单文件上传入库
        """
        
        original_filename = file.filename or "unknown_file" 
        suffix = Path(original_filename).suffix.lower() 
        
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"不支持的文件类型: {suffix}. 支持的类型: {SUPPORTED_EXTENSIONS}")
        
        document_id = uuid.uuid4().hex 
        
        safe_name = f"{document_id}{suffix}" 
        save_path = self.upload_dir / safe_name  
        
        with save_path.open("wb") as f: 
            shutil.copyfileobj(file.file, f) 
        
        raw_documents = load_document_file(save_path)  
        
        if not raw_documents:
            return {
                "document_id": document_id,
                "file_name": original_filename,
                "saved_path": str(save_path),
                "raw_document_count": 0,
                "chunk_count": 0,
                "message": "文件已保存，但未提取到有效文本。若是扫描版 PDF，需要 OCR。",
            } 
        
        enriched_docs: list[Document] = []  
        
        for doc in raw_documents: 
            metadata = dict(doc.metadata or {}) 
            metadata.update(
                {
                    "document_id": document_id,
                    "source_type": source_type,
                    "original_file_name": original_filename,
                }
            )
            
            enriched_docs.append(
                Document(
                    page_content=doc.page_content,
                    metadata=metadata
                )
            ) 
        
        chunks = chunk_documents(
            documents=enriched_docs,
            document_id=document_id
        ) 
        
        vector_count = add_documents_to_vector_store(chunks) 
        bm25_count = save_chunks_to_bm25_store(chunks)
        
        return {
            "document_id": document_id,
            "file_name": original_filename,
            "saved_path": str(save_path),
            "raw_document_count": len(raw_documents),
            "chunk_count": len(chunks),
            "vector_count": vector_count,
            "bm25_count": bm25_count,
            "message": "文件上传并入库成功",
        }
    
    async def upload_many_and_ingest(
        self, 
        files: list[UploadFile],
        source_type: str = "uploaded_file"
    ) -> dict[str, Any]:
        """
        批量上传并入库。

        设计原则：
        - 每个文件独立处理
        - 某个文件失败，不影响其他文件
        - 返回 success_count / failed_count
        """
        
        results: list[dict[str, Any]] = [] 
        
        success_count = 0
        failed_count = 0
        total_chunk_count = 0
        total_vector_count = 0
        total_bm25_count = 0
        
        for file in files: 
            file_name = file.filename or "unknown_file" 
            
            try: 
                result = await self.upload_and_ingest(
                    file=file,
                    source_type=source_type
                )
                
                success_count += 1
                total_chunk_count += int(result.get("chunk_count", 0)) 
                total_vector_count += int(result.get("vector_count", 0))
                total_bm25_count += int(result.get("bm25_count", 0))
                
                results.append(result)
            
            except Exception as exc:
                failed_count += 1

                results.append(
                    {
                        "success": False,
                        "file_name": file_name,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                        "message": "文件上传或入库失败",
                    }
                )
        
        return {
            "total_files": len(files),
            "success_count": success_count,
            "failed_count": failed_count,
            "total_chunk_count": total_chunk_count,
            "total_vector_count": total_vector_count,
            "total_bm25_count": total_bm25_count,
            "results": results,
        }                              
    

 










