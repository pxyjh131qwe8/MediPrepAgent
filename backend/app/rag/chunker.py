from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings


def chunk_documents(
    documents: list[Document],
    document_id: str,
) -> list[Document]:
    """
    将原始 Document 切分为 chunks。

    document_id 用于标记同一个上传文件生成的全部 chunk。
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.RAG_CHUNK_SIZE,
        chunk_overlap=settings.RAG_CHUNK_OVERLAP,
        separators=[
            "\n## ",
            "\n# ",
            "\n\n",
            "\n",
            "。",
            "，",
            " ",
            "",
        ],
    )
    
    chunks = splitter.split_documents(documents)
    
    for index, chunk in enumerate(chunks):
        chunk.metadata = dict(chunk.metadata or {}) 
        chunk.metadata["document_id"] = document_id
        chunk.metadata["chunk_index"] = index
        chunk.metadata["chunk_id"] = f"{document_id}-{index}"

    return chunks
