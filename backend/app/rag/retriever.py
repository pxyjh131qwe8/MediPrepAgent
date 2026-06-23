from pydantic import BaseModel

from app.rag.vector_db import similarity_search


class RetrievedContext(BaseModel):
    content: str 
    source: str 
    title: str 
    score: float 
    


class MedicalRetriever:
    """
    医疗知识检索器
    """
    def retrieve(
        self, 
        query: str,
        top_k: int = 5
    ) -> list[RetrievedContext]:
        
        results = similarity_search(
            query=query,
            top_k=top_k
        ) 
        
        contexts: list[RetrievedContext] = []
        
        for doc, score in results:
            contexts.append(
                RetrievedContext(
                    content=doc.page_content,
                    source=doc.metadata.get("source", ""),
                    title=doc.metadata.get("title", ""),
                    score=float(score) 
                )
            )
        return contexts