"""
FastAPI 应用入口 — 应用的"装配车间"
================================
职责：
1. 创建 FastAPI app 实例
2. 配置 CORS（允许跨域请求）
3. 注册所有业务路由
4. 注册启动/关闭生命周期事件（数据库建表、ChromaDB 初始化等）
5. 全局异常处理

启动命令：uvicorn app.api.main:app --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.config import settings, async_engine
from app.api.routes import (
    health_router,
    department_router,
    risk_router,
    record_router,
    report_router,
    export_router,
    knowledge_router
)


# # 建表函数（在应用启动时调用）
# async_engine = create_async_engine(
#     settings.DATABASE_URL,
#     echo=True,  # 打印SQL语句
#     pool_size=10,  # 连接池大小
#     max_overflow=20,  # 连接池最大溢出数量
# )

async def create_tables():
    """在应用启动时创建数据库表"""
    from app.models.db_models import Base  # 避免循环导入
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ==================== 生命周期管理 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    使用 asynccontextmanager 管理应用启动/关闭。

    启动阶段：
        1. 确保必要目录存在
        2. 创建数据库表
        3. 初始化 HealthAgent 的 PostgreSQL checkpointer（持久化对话记忆）
        4. （后续阶段）连接 Redis

    关闭阶段：
        1. 关闭 Agent checkpointer 连接池
        2. （后续阶段）关闭数据库连接池
        3. （后续阶段）关闭 Redis 连接
    """
    # ===== 启动阶段 =====
    settings.ensure_directories()
    print(f"✅ {settings.APP_NAME} v{settings.APP_VERSION} 启动中...")
    print(f"   📄 数据库: {settings.DATABASE_URL}")
    print(f"   🧠 ChromaDB: {settings.CHROMA_PERSIST_DIR}")
    print(f"   🔴 Redis: {settings.REDIS_URL}")
    print(f"   🤖 LLM 模型: {settings.LLM_MODEL}")
    print(f"   💾 Checkpoint DB: {settings.CHECKPOINT_DATABASE_URL}")

    await create_tables()

    # 初始化 HealthAgent 的 PostgreSQL checkpointer
    from app.api.routes.health import health_service
    await health_service.health_agent.setup_checkpointer()

    yield  # ← 这里是应用正式运行的阶段

    # ===== 关闭阶段 =====
    print(f"🛑 {settings.APP_NAME} 正在关闭...")
    # 释放 PostgreSQL checkpointer 连接池
    try:
        await health_service.health_agent.teardown_checkpointer()
    except Exception:
        pass


# ==================== 创建 FastAPI app ====================

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="医疗问诊智能体后端服务 — 健康档案管理 + LLM 风险评估 + 报告生成",
    lifespan=lifespan,
    docs_url="/docs",       # Swagger UI
    redoc_url="/redoc",     # ReDoc（替代文档风格）
)


# ==================== CORS 中间件 ====================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # 开发阶段允许所有来源
    allow_credentials=True,
    allow_methods=["*"],            # 允许所有 HTTP 方法
    allow_headers=["*"],            # 允许所有请求头
)


# ==================== 全局异常处理 ====================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """兜底异常处理，防止未捕获异常返回 500 堆栈"""
    return JSONResponse(
        status_code=500,
        content={"detail": f"服务器内部错误: {str(exc)}"},
    )


# ==================== 注册路由 ====================

app.include_router(health_router, prefix="/health")
app.include_router(department_router)
app.include_router(risk_router)
app.include_router(record_router)
app.include_router(report_router)
app.include_router(export_router)
app.include_router(knowledge_router, prefix="/api")


# ==================== 根路由（可选，方便快速验证） ====================

@app.get("/", tags=["root"])
async def root():
    """根路由 — 快速确认服务在线"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health/ping",
    }
