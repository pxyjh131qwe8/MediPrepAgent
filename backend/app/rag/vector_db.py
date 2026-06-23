from pathlib import Path 

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

from app.config import settings

# 记得去langchaig官方文档查看一下支持哪些模型
def get_embeddings():
    """
    创建并返回 OpenAIEmbeddings 实例，用于生成文本的向量表示。
    """
    return HuggingFaceEmbeddings(
        model_name=settings.EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    
def get_vector_store() -> Chroma:
    """
    获取Chroma向量库
    """ 
    persist_dir = Path(settings.CHROMA_PERSIST_DIR) 
    persist_dir.mkdir(parents=True, exist_ok=True)  # 确保目录存在
    
    return Chroma(
        collection_name=settings.CHROMA_COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(persist_dir)
    )
    

# def similarity_search(query: str, top_k: int = 5):
#     """
#     对输入的查询文本进行向量化，并在ChromaDB中执行相似度搜索，返回最相关的文档。
#     """
#     vector_store = get_vector_store()
#     results = vector_store.similarity_search_with_score(query, k=top_k)
#     return results


def add_documents_to_vector_store(chunks: list[Document]) -> int:
    """
    将chunks写入Chroma
    """
    if not chunks:
        return 0
    
    vector_store = get_vector_store()
    
    ids = [
        chunk.metadata.get("chunk_id") 
        for chunk in chunks
    ]
    
    vector_store.add_documents(
        documents=chunks,
        ids=ids
    )
    
    return len(chunks)
    
def vector_search(
    query: str,
    top_k: int = 10,
): 
    """
    Chroma向量检索
    
    返回：
    [(Document, distance_score), ...]
    """
    vector_store = get_vector_store()
    results = vector_store.similarity_search_with_score(
        query=query,
        k=top_k
    )
    
    return results



