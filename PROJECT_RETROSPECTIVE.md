# MediPrepAgent 项目复盘书

> 编写日期：2026-06-23 | 版本：v0.1.0

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构全景](#2-系统架构全景)
3. [核心流程详解](#3-核心流程详解)
4. [模块逐一剖析](#4-模块逐一剖析)
5. [关键技术决策](#5-关键技术决策)
6. [踩坑记录](#6-踩坑记录)
7. [可优化点清单](#7-可优化点清单)
8. [经验总结](#8-经验总结)

---

## 1. 项目概述

### 1.1 定位

MediPrepAgent 是一个**智能就诊准备助手**，目标用户在就诊前使用。它不做诊断、不开药，只提供三件事：

| 功能 | 说明 |
|------|------|
| 健康科普 | 根据症状，结合 RAG 检索的医学知识进行解释 |
| 科室推荐 | 给出首推科室 + 备选科室 + 理由 |
| 就诊清单 | 就诊前要准备什么（资料、问题、注意事项） |

### 1.2 核心安全红线

```
1. 不能做疾病确诊
2. 不能替代医生诊疗
3. 不能推荐处方药、剂量或具体治疗方案
4. 只能做健康科普、风险提示、科室导航和就诊准备
5. 用户明确否认的症状（"没有胸痛"），不得当作阳性高危信号
```

### 1.3 技术栈总览

| 层 | 技术 | 版本 |
|----|------|------|
| Web 框架 | FastAPI + Uvicorn | ≥0.115 / ≥0.30 |
| 配置 | pydantic-settings | ≥2.0 |
| ORM | SQLAlchemy 2.0 async | ≥2.0.30 |
| 数据库 | SQLite(开发) / MySQL(生产) | — |
| 向量库 | ChromaDB (langchain-chroma) | — |
| Embedding | BAAI/bge-small-zh-v1.5 (HuggingFace, CPU) | — |
| BM25 | rank_bm25 + jieba | — |
| Rerank | DashScope qwen3-rerank | — |
| LLM | DeepSeek deepseek-chat | — |
| Agent 框架 | LangChain create_agent + LangGraph | ≥0.2 |
| Checkpointer | AsyncPostgresSaver (PostgreSQL) | — |
| 文档加载 | pypdf / python-docx | — |

---

## 2. 系统架构全景

```mermaid
flowchart TB
    subgraph Client["👤 客户端"]
        C1["POST /health/consult"]
        C2["POST /api/knowledge/upload"]
        C3["POST /api/knowledge/search"]
    end

    subgraph Gateway["🌐 FastAPI 网关"]
        G1["CORS 中间件"]
        G2["lifespan 生命周期"]
    end

    subgraph Orchestrator["⚙️ HealthService"]
        O1["① 合并历史上下文（可选）"]
        O2["② RAG 检索"]
        O3["③ Agent 推理"]
        O4["④ 保存上下文"]
    end

    subgraph RAG["🔎 混合检索管线"]
        R1["ChromaDB 向量召回<br/>top_k=12"]
        R2["BM25 关键词召回<br/>top_k=12"]
        R3["分数融合<br/>0.55×Vec + 0.45×BM25"]
        R4["候选截断<br/>max 20"]
        R5["DashScope Rerank<br/>→ top 5"]
        R1 --> R3
        R2 --> R3
        R3 --> R4 --> R5
    end

    subgraph Agent["🤖 HealthAgent"]
        A1["System Prompt<br/>安全边界 + JSON Schema"]
        A2["Safety Tool<br/>硬约束"]
        A3["SummarizationMiddleware<br/>6条触发摘要 / 保留2条"]
        A4["AsyncPostgresSaver<br/>PostgreSQL 持久化"]
        A5["DeepSeek LLM<br/>deepseek-chat"]
        A1 --> A5
        A2 --> A5
        A3 --> A5
        A4 --> A5
    end

    subgraph Data["💿 数据层"]
        D1["业务库 (SQLite/MySQL)<br/>health_records<br/>health_session_contexts"]
        D2["Checkpoint库 (PostgreSQL)<br/>LangGraph 消息历史"]
        D3["ChromaDB<br/>向量持久化"]
        D4["rag_chunks.jsonl<br/>BM25 索引"]
        D5["文件存储<br/>medical_guides/ + uploads/"]
    end

    Client --> Gateway --> Orchestrator
    Orchestrator --> RAG --> Agent
    Orchestrator --> D1
    Agent --> D2
    RAG --> D3 & D4
```

### 2.1 架构分层

```
┌─────────────────────────────────────────┐
│  API 层    │ routes/*.py                │  ← 路由定义，参数校验
├─────────────────────────────────────────┤
│  服务层    │ services/*.py              │  ← 主编排、上下文、知识库管理
├─────────────────────────────────────────┤
│  智能体层  │ agents/health_agent.py     │  ← LangChain Agent + Tools
├─────────────────────────────────────────┤
│  RAG 层    │ rag/*.py                   │  ← 检索管线（向量/BM25/Rerank）
├─────────────────────────────────────────┤
│  模型层    │ models/*.py                │  ← ORM + Pydantic Schema
├─────────────────────────────────────────┤
│  数据层    │ data/ + PostgreSQL + SQLite│  ← 持久化存储
└─────────────────────────────────────────┘
```

---

## 3. 核心流程详解

### 3.1 健康咨询主链路

```mermaid
sequenceDiagram
    participant C as 👤 客户端
    participant API as 🌐 FastAPI
    participant HS as ⚙️ HealthService
    participant CTX as 💾 HealthContextService
    participant RAG as 🔎 MedicalRAGTool
    participant HA as 🤖 HealthAgent
    participant DB as 🗄️ PostgreSQL/SQLite

    C->>API: POST /health/consult
    API->>HS: consult_health(request)
    
    alt use_saved_context = true
        HS->>CTX: merge_with_saved_context()
        CTX->>DB: SELECT health_session_contexts
        DB-->>CTX: 历史画像
        CTX-->>HS: 合并后的 request
    end

    HS->>RAG: search_medical_knowledge(symptoms, top_k=5)
    RAG->>RAG: ① ChromaDB 向量召回 ② BM25 召回 ③ 融合 ④ Rerank
    RAG-->>HS: contexts + references

    HS->>HA: generate(input, thread_id)
    HA->>DB: 从 checkpoint 恢复历史消息
    HA->>HA: DeepSeek ReAct 推理
    HA-->>HS: HealthAgentOutput (JSON)

    HS->>CTX: save_from_consult_request()
    CTX->>DB: UPSERT health_session_contexts

    HS-->>API: HealthConsultResponse
    API-->>C: JSON 响应
```

### 3.2 Agent 内部 ReAct 循环

```
用户输入 "头痛三天，太阳穴跳痛"
    ↓
System Prompt 注入（安全规则 + 输出 Schema）
    ↓
从 AsyncPostgresSaver 恢复历史消息（根据 thread_id）
    ↓
SummarizationMiddleware 检查消息数 > 6？
    ├── 是 → 调用 DeepSeek 生成摘要，只保留最近 2 条
    └── 否 → 完整传递
    ↓
Agent 思考 → 需要调用 safety_rule_tool？
    ├── 是 → 调用 tool，获得安全边界声明
    └── 否 → 直接输出
    ↓
输出结构化 JSON → HealthAgentOutput
    ↓
解析失败？→ 四级降级 → fallback_output
```

### 3.3 RAG 检索三级管线

```
输入 query = "头痛三天太阳穴跳痛"

第一级：双路并行召回（各 12 条）
┌──────────────────────────────────────────────────────┐
│ ChromaDB 语义召回                                      │
│ BGE-small-zh 向量化 query → cosine_similarity          │
│ distance → similarity = 1/(1+distance)                │
│ 结果：语义相近但可能缺少精确术语匹配的 chunk             │
├──────────────────────────────────────────────────────┤
│ BM25 关键词召回                                        │
│ jieba.lcut(query) → ["头痛", "三天", "太阳穴", "跳痛"]  │
│ BM25Okapi 计算词频-逆文档频率得分                        │
│ 结果：精确匹配"头痛""太阳穴"等关键词的 chunk              │
└──────────────────────────────────────────────────────┘

第二级：分数融合
┌──────────────────────────────────────────────────────┐
│ 各自 min-max 归一化到 [0,1]                             │
│ hybrid_score = 0.55 × vector + 0.45 × bm25            │
│ 按 hybrid_score 降序，截断 top(4 × final_top_k) ≤ 20   │
└──────────────────────────────────────────────────────┘

第三级：Cross-Encoder 精排
┌──────────────────────────────────────────────────────┐
│ 候选截取前 3000 字符                                    │
│ POST DashScope qwen3-rerank                           │
│ 每个候选获得 rerank_score                              │
│ 按 rerank_score 降序 → 最终 top 5                       │
│ 失败降级 → hybrid_score 排序                            │
└──────────────────────────────────────────────────────┘
```

### 3.4 知识摄入流程

```
输入文件 (PDF/DOCX/TXT/MD)
    ↓
document_loader.load_document_file()
    ├── PDF  → pypdf.PdfReader, 按页拆分为 Document
    ├── DOCX → python-docx.Document, 全文一个 Document
    └── TXT/MD → open().read(), utf-8/gbk 自动检测
    ↓
chunker.chunk_documents()
    ├── RecursiveCharacterTextSplitter
    ├── chunk_size=700, overlap=120
    ├── 分隔符优先级: ## → # → 空行 → 句号 → 逗号
    └── 每个 chunk 获得 chunk_id = "{uuid}-{index}"
    ↓
双写存储
├── vector_db.add_documents_to_vector_store()
│   ├── HuggingFaceEmbeddings 向量化
│   └── Chroma.add_documents() → chroma_db/
└── bm25_store.save_chunks_to_bm25_store()
    ├── BM25ChunkRecord(chunk_id, content, metadata)
    └── JSONL 追加写入 rag_chunks.jsonl（chunk_id 去重）
```

---

## 4. 模块逐一剖析

### 4.1 配置模块 (`config.py`)

```python
class Settings(BaseSettings):
    # 应用基础
    APP_NAME: str = "MediPrepAgent"
    APP_VERSION: str = "0.1.0"

    # 数据库（业务数据）
    DATABASE_URL: str = "mysql+aiomysql://user:password@localhost:3306/mediprep_db"

    # 向量数据库
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    CHROMA_PERSIST_DIR: str = "data/chroma_db"

    # LLM
    LLM_MODEL: str = "deepseek-chat"
    LLM_BASE_URL: str = "https://api.deepseek.com"

    # RAG 参数
    RAG_CHUNK_SIZE: int = 700
    RAG_CHUNK_OVERLAP: int = 120
    RAG_VECTOR_TOP_K: int = 12
    RAG_BM25_TOP_K: int = 12
    RAG_FINAL_TOP_K: int = 5
    RAG_VECTOR_WEIGHT: float = 0.55
    RAG_BM25_WEIGHT: float = 0.45

    # Checkpoint（对话记忆）
    CHECKPOINT_DATABASE_URL: str = "postgresql://user:password@localhost:5432/mediprep_checkpoints"
```

**设计要点**：
- 使用 pydantic-settings 自动从 `.env` 加载，环境变量优先级最高
- 所有参数有默认值，开发环境开箱即用
- `ensure_directories()` 在启动时自动创建需要的目录

### 4.2 API 网关 (`api/main.py`)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动：建目录 → 建表 → 初始化 checkpointer"""
    settings.ensure_directories()
    await create_tables()                          # 业务表
    await health_service.health_agent.setup_checkpointer()  # Agent 记忆
    yield
    """关闭：释放 checkpointer 连接池"""
    await health_service.health_agent.teardown_checkpointer()
```

**设计要点**：
- 使用 `asynccontextmanager` 管理生命周期，FastAPI 原生支持
- CORS 全开（开发阶段），生产需收紧
- 全局异常处理通过 `@app.exception_handler` 兜底

### 4.3 主编排器 (`services/health_service.py`)

```python
class HealthService:
    def __init__(self):
        self.health_agent = HealthAgent()
        self.context_service = HealthContextService()
        self.rag_tool = MedicalRAGTool()

    async def consult_health(request, db) -> HealthConsultResponse:
        # ① 可选合并历史上下文
        if request.use_saved_context:
            request = await self.context_service.merge_with_saved_context(db, request)

        # ② RAG 检索
        rag_context, references = self.rag_tool.search_medical_knowledge(
            request.symptoms, top_k=5)

        # ③ Agent 推理（风险、科室均由 LLM 输出，不用规则引擎）
        agent_output = await self.health_agent.generate(
            HealthAgentInput(user_request=request, rag_context=rag_context),
            thread_id=request.thread_id)

        # ④ 保存上下文
        await self.context_service.save_from_consult_request(db, request)

        return HealthConsultResponse(
            summary=agent_output.summary,
            risk_result=agent_output.risk_result,
            department_result=agent_output.department_result,
            references=references,
            disclaimer="本结果仅用于健康科普...")
```

**设计要点**：
- 主编排器模式：只做编排，不写业务逻辑
- `risk_service` / `department_service` 已注释废弃，风险/科室全由 LLM 输出
- 每个步骤职责单一，方便替换和测试

### 4.4 Agent 模块 (`agents/health_agent.py`)

```python
class HealthAgent:
    SYSTEM_PROMPT = """你是 MediPrepAgent...（安全规则 + 输出 JSON Schema）"""

    def __init__(self):
        self.checkpointer = InMemorySaver()           # 降级兜底
        self.middleware = SummarizationMiddleware(
            model=settings.LLM_MODEL,
            trigger=("messages", 6),
            keep=("messages", 2))
        self.agent = create_agent(
            model=settings.LLM_MODEL,
            tools=[medical_safety_rule_tool],
            system_prompt=self.SYSTEM_PROMPT,
            checkpointer=self.checkpointer,
            middleware=[self.middleware])

    async def setup_checkpointer(self):
        """lifespan 调用，升级为 PostgreSQL 持久化"""
        self._pg_context = AsyncPostgresSaver.from_conn_string(
            settings.CHECKPOINT_DATABASE_URL)
        pg = await self._pg_context.__aenter__()
        await pg.setup()
        self.checkpointer = pg
        self.agent = create_agent(...)  # 用新 checkpointer 重建

    async def generate(self, agent_input, thread_id):
        config = {"configurable": {"thread_id": thread_id}}
        result = await self.agent.ainvoke(
            {"messages": [HumanMessage(content=user_prompt)]}, config=config)
        return self._parse_json_output(raw_text)
```

**设计要点**：
- `__init__` 中先用 `InMemorySaver`，保证构造不会失败
- `setup_checkpointer()` 在 lifespan 中调用，升级到 PostgreSQL
- PostgreSQL 连接失败 → 保留 InMemorySaver → 打印警告 → 服务正常
- `create_agent` 调用两次（初始化时 + setup 后），确保 agent 引用最新 checkpointer
- `SummarizationMiddleware` 自动压缩长对话，防止 token 溢出

**四级 JSON 降级**：
```
① Markdown 代码块剥离（```json ... ```→ 纯文本）
② JSON 提取（找到第一个 { 和最后一个 }）
③ json.loads() 解析
④ 失败 → fallback_output() 返回友好默认建议
```

### 4.5 混合检索器 (`rag/hybrid_retriever.py`)

```python
class HybridMedicalRetriever:
    def retrieve(self, query, final_top_k=5):
        # ① 双路召回
        vector_results = vector_search(query, top_k=12)
        bm25_results = bm25_search(query, top_k=12)

        # ② 归一化 + 融合
        for each chunk:
            normalized_vector = score / max_vector_score
            normalized_bm25 = score / max_bm25_score
            hybrid_score = 0.55 * normalized_vector + 0.45 * normalized_bm25

        # ③ 截断 (max 20)
        candidates = top(hybrid_scores, 4 * final_top_k)[:20]

        # ④ Rerank
        try:
            reranked = self.reranker.rerank(query, candidates)
            return reranked[:final_top_k]
        except:
            return sorted_by_hybrid_score[:final_top_k]  # 降级
```

### 4.6 向量库 (`rag/vector_db.py`)

```python
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-zh-v1.5",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True})

def get_vector_store():
    return Chroma(
        collection_name="medical_guides",
        embedding_function=get_embeddings(),
        persist_directory="data/chroma_db")

def vector_search(query, top_k):
    store = get_vector_store()
    return store.similarity_search_with_score(query, k=top_k)
    # 返回 [(Document, distance_score), ...]
```

**注意**：Chroma 返回的是 **distance**（越小越相似），需要转换为 similarity。

### 4.7 BM25 存储 (`rag/bm25_store.py`)

```python
class BM25ChunkRecord(BaseModel):
    chunk_id: str
    content: str
    metadata: dict

def bm25_search(query, top_k):
    # 加载 JSONL → jieba 分词 → BM25Okapi → get_scores()
    records = load_all_chunks()        # 从 rag_chunks.jsonl
    corpus = [jieba.lcut(r.content) for r in records]
    bm25 = BM25Okapi(corpus)
    query_tokens = jieba.lcut(query)
    scores = bm25.get_scores(query_tokens)
    # 返回 top_k
```

**设计要点**：
- JSONL 格式存储，每行一个 chunk，方便追加
- `chunk_id` 去重：写入前检查是否已存在
- 每次检索都重新加载文件 → 小数据量够用，大数据量需优化

### 4.8 DashScope Reranker (`rag/dashscope_reranker.py`)

```python
class DashScopeReranker:
    def rerank(self, query, candidates):
        response = requests.post(
            "https://dashscope.aliyuncs.com/compatible-api/v1/reranks",
            headers={"Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}"},
            json={
                "model": "qwen3-rerank",
                "query": query,
                "documents": [c.content[:3000] for c in candidates],
                "instruction": "关注医学相关性..."  # medical-specific
            })
        # 按 relevance_score 降序返回
```

### 4.9 上下文管理 (`services/health_context_service.py`)

```python
class HealthContextService:
    async def merge_with_saved_context(db, request):
        """合并历史上下文：本次输入优先，历史兜底"""
        context = await get_context(db, request.thread_id)
        return HealthConsultRequest(
            age=request.age or context.age,             # 本次有就用本次
            gender=request.gender or context.gender,
            symptoms=request.symptoms or context.latest_symptoms,
            ...
        )

    async def save_from_consult_request(db, request):
        """咨询完成后保存本次病情"""
        await upsert_context(db, HealthContextUpdateRequest(...))
```

### 4.10 知识库管理 (`services/knowledge_service.py`)

```python
class KnowledgeService:
    async def upload_and_ingest(file, source_type):
        # ① 保存文件到 data/uploads/knowledge/{uuid}.ext
        # ② 加载文档 → document_loader.load_document_file()
        # ③ 切片 → chunker.chunk_documents()
        # ④ 双写 → vector_db + bm25_store
        # ⑤ 返回 chunk 数量
```

### 4.11 数据模型

```sql
-- 业务表（SQLAlchemy 管理，SQLite/MySQL）
health_records:
    id, symptoms, duration, request_json, result_json, create_time, update_time

health_session_contexts:
    id, thread_id (UNIQUE), age, gender, latest_symptoms,
    duration, medical_history, medication_history, allergy_history,
    create_time, update_time

report_records:
    id, report_text, result_json, create_time, update_time

-- Checkpoint 表（LangGraph 自动管理，PostgreSQL）
-- 由 AsyncPostgresSaver.setup() 自动创建
-- 存储序列化的消息历史、channel_values 等
```

---

## 5. 关键技术决策

### 5.1 为什么弃用规则引擎？

最初单独实现了 `RiskService`（关键词匹配判断风险等级）和 `DepartmentService`（关键词字典映射科室）。实践中发现：

- **漏判严重**：关键词列表无法穷尽所有表达方式（"胸口闷"没匹配到"胸痛"关键词）
- **误判频繁**：用户在上下文中说"没有胸痛"，关键词匹配仍触发 HIGH
- **维护成本高**：医学症状表述千变万化，规则列表需要专家持续维护

**决策**：改为由 LLM Agent 在 System Prompt 中完成风险判断和科室推荐，Agent 能理解语义而非关键词。规则服务代码保留但不再参与主流程。

### 5.2 为什么用混合检索而非纯向量？

- 纯向量检索对医学术语的精确匹配不够敏感（"布洛芬"和"对乙酰氨基酚"在向量空间很近但完全不是同一种药）
- 纯 BM25 无法捕捉语义相近但用词不同的内容（"太阳穴跳痛"和"偏头痛"在 BM25 中完全不同）
- **混合检索 = 语义召回 + 关键词精准匹配**，互补长短

### 5.3 为什么加 Rerank？

向量检索和 BM25 都是双塔模型（query 和 document 独立编码），对 query-document 的深层交互理解不足。Cross-encoder Rerank 将 query 和 document 拼接后编码，能捕获更细腻的相关性。

### 5.4 为什么选择 AsyncPostgresSaver 而非 SqliteSaver？

| 维度 | SqliteSaver | AsyncPostgresSaver |
|------|-------------|-------------------|
| 并发 | 文件锁，写串行 | MVCC，高并发 |
| 多实例 | 不支持 | 天然支持 |
| 异步 | 同步阻塞 | 原生 async |
| 持久化 | ✅ | ✅ |
| 运维 | 零依赖 | 需要 PG 实例 |
| 适用 | 单机开发 | 生产环境 |

### 5.5 为什么不让 Agent 直接做诊断？

医疗场景容错率极低，LLM 幻觉可能导致严重后果。通过 System Prompt 硬约束 + Safety Tool 双重保障，确保系统只在安全边界内运作。响应末尾始终附带 `disclaimer` 声明。

---

## 6. 踩坑记录

### 坑 1：AsyncPostgresSaver.from_conn_string() 返回上下文管理器

**现象**：`'_AsyncGeneratorContextManager' object has no attribute 'setup'`

**原因**：`from_conn_string()` 返回的是 `AsyncGeneratorContextManager`，不是 checkpointer 实例。必须 `__aenter__()` 进入上下文才能拿到实例。

**解决**：
```python
self._pg_context = AsyncPostgresSaver.from_conn_string(url)
pg = await self._pg_context.__aenter__()
await pg.setup()
```

**教训**：LangGraph 的 PostgreSQL checkpointer 设计为上下文管理器模式，因为它内部维护 psycopg 连接池，需要用 `__aexit__` 清理。

### 坑 2：ChromaDB 返回 distance 而非 similarity

**现象**：向量检索结果的分数与其他通路无法直接比较

**解决**：`similarity = 1.0 / (1.0 + distance)`

### 坑 3：BM25 分数无固定范围

**现象**：BM25 得分取决于语料库大小，无法与向量相似度直接融合

**解决**：各自独立 min-max 归一化到 [0,1] 后再加权融合

### 坑 4：create_agent 引用的是旧的 checkpointer

**现象**：`setup_checkpointer()` 更新了 `self.checkpointer`，但 agent 仍使用初始化时的 InMemorySaver

**原因**：`create_agent()` 在构造时将 checkpointer 内嵌到 agent 的 graph 中，后续修改 `self.checkpointer` 不会自动生效

**解决**：`setup_checkpointer()` 中重新调用 `create_agent()` 重建整个 agent

---

## 7. 可优化点清单

### 🔴 高优先级（影响功能/稳定性）

| # | 问题 | 现状 | 建议 |
|---|------|------|------|
| 1 | BM25 每次检索全量加载 JSONL | 小规模 OK，万级 chunk 会卡 | 改为启动时加载到内存，文件变更时增量更新 |
| 2 | ChromaDB 每次检索重新初始化连接 | 每次 `get_vector_store()` 新建 Chroma 实例 | 单例模式，启动时初始化一次 |
| 3 | 无请求限流 | 任何人都可以无限调用 | 加 `slowapi` 或 Redis 令牌桶限流 |
| 4 | CORS 全开 | `allow_origins=["*"]` | 生产环境改为白名单 |
| 5 | HealthAgent 在 `main.py` 中通过 `health_service` 间接引用 | 耦合较深 | 考虑将 checkpointer 初始化抽到独立的 `startup.py` |

### 🟡 中优先级（影响性能/体验）

| # | 问题 | 现状 | 建议 |
|---|------|------|------|
| 6 | Embedding 模型在 CPU 运行 | 首次加载慢，推理慢 | 加本地模型缓存；后续可换 GPU 或 API |
| 7 | 无 checkpoint 清理机制 | 消息历史无限增长 | 加 TTL 定时清理（7天未活跃的 thread） |
| 8 | 无对话轮次限制 | 单 thread 可无限对话 | 加 max_turns 限制，超出后提示新建会话 |
| 9 | SummarizationMiddleware 参数偏保守 | 6条触发/保留2条，DeepSeek 64K | 可调到 12条触发/保留4条 |
| 10 | 无流式输出 (SSE) | 用户需等待完整响应 | 改为 StreamingResponse，逐 token 推送 |
| 11 | 无 RAG 检索缓存 | 相同 query 重复检索 | Redis 缓存检索结果，TTL=1h |

### 🟢 低优先级（锦上添花）

| # | 问题 | 现状 | 建议 |
|---|------|------|------|
| 12 | 无用户认证 | 任何人均可调用 | 加 JWT 或 API Key 认证 |
| 13 | 无监控/日志 | 只有 print() | 接入 structlog / Prometheus / Sentry |
| 14 | 无 Docker 部署 | 手动启动 | 写 Dockerfile + docker-compose.yml |
| 15 | 无单元测试 | 只有测试框架声明 | 补 pytest 用例（至少覆盖降级逻辑） |
| 16 | 遗留代码未清理 | risk_service / department_service 废弃但文件保留 | 删除或移动到 `deprecated/` |
| 17 | InMemorySaver / SqliteSaver import 未清理 | health_agent.py 顶部保留了未使用的 import | 清理 `from langgraph.checkpoint.sqlite import SqliteSaver` 和 `import sqlite3` |
| 18 | `api/main.py` 中冗余的 import | `create_async_engine` 等在 config.py 已定义 | 清理未使用的 import |

### 🔵 架构级优化

| # | 方向 | 详细说明 |
|---|------|----------|
| 19 | **RAG 评估体系** | 当前无量化手段衡量检索质量。建议：构建标注数据集，计算 Recall@K、MRR、NDCG 等指标，对比纯向量/纯 BM25/混合 的效果差异 |
| 20 | **多模态 RAG** | 医学指南常含表格、流程图。当前只处理文本，建议引入表格解析（如 camelot/tabula）和图片 OCR |
| 21 | **用户反馈闭环** | 收集用户对推荐科室/科普内容的满意度，用于 fine-tune Rerank 权重或调整检索策略 |
| 22 | **A/B 测试框架** | 对比不同 System Prompt、不同 LLM、不同检索参数的效果，量化优化收益 |

---

## 8. 经验总结

### 8.1 架构层面

1. **主编排器模式值得坚持**：`HealthService` 只做编排不写业务逻辑，每个子服务职责单一，替换和测试都很方便
2. **降级是必选项不是加分项**：RAG 管线的每个环节（Rerank → hybrid → BM25）、Agent 输出解析（JSON parse → fallback）、Checkpointer（PG → InMemory）都有降级路径，保证了系统在任何异常下都有可用响应
3. **Agent 记忆需要"热升级"**：`__init__` 中 InMemorySaver 兜底 + `setup_checkpointer()` 热升级的模式，让 Agent 构造不依赖外部基础设施，服务启动更鲁棒

### 8.2 Agent 层面

4. **安全约束要双重保障**：System Prompt（软约束）+ Safety Tool（硬拦截），单靠 Prompt 不够可靠
5. **否认症状处理是 Agent 的难点**：用户说"没有胸痛"，LLM 可能错误地将其与胸痛关联。System Prompt 中需要反复强调"否认 ≠ 阳性"
6. **输出 Schema 约束比开放式输出安全**：强制 JSON 格式，字段可控，前端解析稳定

### 8.3 RAG 层面

7. **混合检索比单一方案好得多**：向量提供语义泛化，BM25 提供精确匹配，Rerank 提供深度交互——三级架构互补效果明显
8. **BM25 对中文需要分词**：直接用英文的分词器效果很差，`jieba` 是中文场景的必需品
9. **EMBEDDING 模型选择影响全局**：BGE-small-zh 轻量且效果不错，但 CPU 推理慢是瓶颈

### 8.4 工程层面

10. **异步全链路很重要**：从 FastAPI → SQLAlchemy → Agent → Checkpointer，全链路 `async/await`，没有同步阻塞点
11. **pydantic-settings 统一配置管理**：所有参数一个 `Settings` 类，自动从 `.env` 加载，IDE 有类型提示，比散落的 `os.getenv()` 好太多
12. **LangGraph 的上下文管理器设计需要提前了解**：`from_conn_string()` 不是工厂方法而是上下文管理器，这个设计容易踩坑

---

> **复盘人**：开发者 | **日期**：2026-06-23
>
> 本项目从零搭建，经历多次重构（规则引擎弃用、混合检索引入、checkpointer 从 InMemory → SQLite 尝试 → PostgreSQL 落地），当前版本可用于演示和继续迭代。
