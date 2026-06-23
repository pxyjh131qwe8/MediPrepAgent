from pathlib import Path
import sys 

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter 
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# 让脚本能找到app包
BASE_DIR = Path(__file__).resolve().parents[1] 
sys.path.append(str(BASE_DIR)) 

from app.config import settings  

def load_markdown_documents() -> list[Document]:
    """
    从指定目录加载 Markdown 文件，并将其转换为 Document 对象列表。
    """ 
    docs_dir = Path(settings.MEDICAL_DOCS_DIR) 
    
    if not docs_dir.exists():
        raise FileNotFoundError(f"医疗知识库目录不存在: {docs_dir}") 
    
    documents: list[Document] = [] 
    
    for file_path in docs_dir.glob("*.md"):
        text = file_path.read_text(encoding="utf-8")
        
        doc = Document(
            page_content=text,
            metadata={
                "source": str(file_path),
                "title": file_path.stem,
                "file_name": file_path.name
            }
        )
        documents.append(doc)
    
    return documents


def split_documents(documents: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=100,
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
        chunk.metadata["chunk_id"] = index

    return chunks


def ingest():
    documents = load_markdown_documents() 
    
    if not documents:
        print("没有找到任何markdown医疗文档") 
        return 
    
    chunks = split_documents(documents) 
    
    print(f"加载文档数量：{len(documents)}")
    print(f"切片数量：{len(chunks)}")
    
    embeddings = HuggingFaceEmbeddings(
        model_name=settings.EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    
    persist_dir = Path(settings.CHROMA_PERSIST_DIR) 
    persist_dir.mkdir(parents=True, exist_ok=True) 
    
    # 先清空旧的collection
    vector_store = Chroma(
        collection_name=settings.CHROMA_COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(persist_dir),
    )
    
    try: 
        vector_store.delete_collection() 
        print("已清空旧的Chroma collection") 
    except Exception as e:
        print(f"清空旧的Chroma collection失败: {e}")
    
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=settings.CHROMA_COLLECTION_NAME,
        persist_directory=str(persist_dir),
    )
    
    print("医疗知识入库完成!")


if __name__ == "__main__":
    ingest()        