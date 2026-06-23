"""
MediPrepAgent 全局配置模块
=======================
使用 pydantic-settings 从环境变量 / .env 文件加载配置。
所有配置项均有类型校验和默认值，避免运行时出现 None 值。
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


class Settings(BaseSettings):
    """
    应用全局配置

    加载优先级（由高到低）：
    1. 系统环境变量
    2. .env 文件
    3. 字段默认值
    """

    # ==================== 应用基础 ====================
    APP_NAME: str = Field(
        default="MediPrepAgent",
        description="应用名称，用于 FastAPI docs 标题"
    )
    APP_VERSION: str = Field(default="0.1.0", description="应用版本号")
    DEBUG: bool = Field(default=True, description="调试模式开关")

    # ==================== 数据库 ====================
    DATABASE_URL: str = Field(
        default="",
        description="数据库连接字符串，例如 mysql+aiomysql://user:password@localhost:3306/mediprep_db?charset=utf8"
    )

    # ==================== ChromaDB 向量数据库 ====================
    MEDICAL_DOCS_DIR: str = "data/medical_guides"
    CHROMA_PERSIST_DIR: str = "data/chroma_db"
    CHROMA_COLLECTION_NAME: str = "medical_guides"
    # 本地中文 embedding 模型
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"

    # ==================== Redis 缓存 ====================
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis 连接地址"
    )

    # ==================== LLM 配置 ====================
    LLM_API_KEY: str = Field(
        default="",
        description="大模型 API Key（OpenAI / 兼容接口）"
    )
    LLM_BASE_URL: str = Field(
        default="https://api.deepseek.com",
        description="大模型 API 基础地址"
    )
    LLM_MODEL: str = Field(
        default="deepseek-chat",
        description="默认使用的 LLM 模型名称"
    )
    
    # ==================== RAG 文件上传与检索配置 ====================
    UPLOAD_DOCS_DIR: str = "data/uploads/knowledge"

    RAG_CHUNKS_PATH: str = "data/rag_chunks.jsonl"

    RAG_CHUNK_SIZE: int = 700
    RAG_CHUNK_OVERLAP: int = 120

    RAG_VECTOR_TOP_K: int = 12
    RAG_BM25_TOP_K: int = 12
    RAG_FINAL_TOP_K: int = 5

    RAG_VECTOR_WEIGHT: float = 0.55
    RAG_BM25_WEIGHT: float = 0.45

    # DashScope Rerank
    DASHSCOPE_API_KEY: str = Field(
        default="",
        description="阿里云 DashScope API Key，用于 Rerank 重排序"
    )
    DASHSCOPE_RERANK_MODEL: str = "qwen3-rerank"
    DASHSCOPE_RERANK_ENABLED: bool = True

    # ==================== Agent Checkpoint（PostgreSQL 持久化记忆） ====================
    CHECKPOINT_DATABASE_URL: str = Field(
        default="",
        description="LangGraph checkpoint 存储（PostgreSQL，持久化对话历史），例如 postgresql://user:password@localhost:5432/mediprep_checkpoints"
    )

    # ==================== 服务端口 ====================
    HOST: str = Field(default="0.0.0.0", description="服务监听地址")
    PORT: int = Field(default=8000, description="服务监听端口")

    # ==================== 自动创建目录 ====================
    def ensure_directories(self) -> None:
        """确保必要目录存在"""
        Path("data").mkdir(parents=True, exist_ok=True)
        Path(self.MEDICAL_DOCS_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.UPLOAD_DOCS_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.RAG_CHUNKS_PATH).parent.mkdir(parents=True, exist_ok=True)

    model_config = {
        "env_file": ".env",           # 自动读取项目根目录的 .env
        "env_file_encoding": "utf-8",
        "case_sensitive": True,       # 保持大写风格
    }


# 全局单例 —— 项目任何地方 from app.config import settings 即可使用
settings = Settings()


# 建表函数（在应用启动时调用）
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,  # 打印SQL语句
    pool_size=10,  # 连接池大小
    max_overflow=20,  # 连接池最大溢出数量
)

# 全局异步数据库会话工厂，供依赖注入使用
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, # 绑定异步引擎
    class_=AsyncSession, # 使用异步会话类
    expire_on_commit=False, # 提交后会话不过期，不会重新查询数据库
)

# 写依赖函数，作用是统一规划每次路由运行时，创建、管理、关闭session的流程
async def get_database():
    async with AsyncSessionLocal() as session:
        try:
            yield session   # 返回数据库会话给路由处理函数
            await session.commit() # 提交事务
        except Exception as e:
            await session.rollback() # 回滚事务
            raise e
        finally:
            await session.close() # 关闭会话

