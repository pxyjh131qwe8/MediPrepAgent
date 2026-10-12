# MediPrepAgent

MediPrepAgent 是一个完整的智能就诊准备项目。它通过多 Agent 协作完成急症信号识别、医学资料检索、科室建议、就诊清单和安全复核，但不做疾病诊断，也不替代医生。

## 现在包含什么

- React + TypeScript 响应式咨询工作台
- FastAPI API 与 SQLite/MySQL 持久化
- 五角色协作：安全分诊、证据检索、就诊规划、安全复核、温柔表达
- 中文否定词识别，例如“没有胸痛”不会被当作胸痛
- 可追溯的资料摘录与 Agent 协作轨迹
- Chroma + BGE + BM25 + DashScope Rerank 可选增强检索
- LLM 不可用时的保守降级结果
- 同一会话下的结构化健康上下文续问

## 安全边界

医疗建议无法仅凭线上文字保证绝对准确。MediPrep 采用以下机制降低误导风险：

1. 急症分诊由确定性规则先行，生成模型不能降低风险等级。
2. 明确否认的症状同时从分诊和证据检索中排除。
3. LLM 只负责整理就诊计划，不能确诊、开药或给药物剂量。
4. 最终结果经过独立安全复核，并只保留真实检索到的来源。
5. 没有足够资料时明确展示限制，不补写虚假医学依据。

> 如果正在出现胸痛伴呼吸困难或大汗、意识异常、昏迷、抽搐、新发肢体无力、说话不清、大量出血等情况，请直接联系 120 或前往急诊，不要等待在线结果。

## 架构

```text
用户描述
  ├─ 安全分诊 Agent ─────────────┐
  └─ 证据检索 Agent（并行）──────┤
                                  ▼
                           就诊规划 Agent
                                  ▼
                           医疗安全复核 Agent
                                  ▼
                           温柔表达 Agent
                                  ▼
          风险 + 科室 + 清单 + 来源 + 协作轨迹
```

## 快速启动

推荐 Python 3.11+、Node.js 18+。当前前端也兼容 Node.js 16。

### 1. 安装后端核心依赖

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

不配置 `DATABASE_URL` 时默认使用本地 SQLite。不配置 `LLM_API_KEY` 时，系统仍能运行，并返回保守的规则结果与内置指南依据。

### 2. 构建前端

```powershell
cd ..\frontend
npm install
npm run build
```

### 3. 启动完整应用

```powershell
cd ..\backend
.venv\Scripts\python.exe -m uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

打开 [http://localhost:8000](http://localhost:8000)。API 文档位于 [http://localhost:8000/docs](http://localhost:8000/docs)。FastAPI 会自动托管 `frontend/dist`。

## 前端开发模式

后端保持在 8000 端口，再启动：

```powershell
cd frontend
npm run dev
```

打开 [http://localhost:5173](http://localhost:5173)。Vite 会把 `/health` 和 `/api` 请求代理到后端。

## 启用增强 RAG

核心安装会直接使用 `backend/data/medical_guides` 中的内置指南。需要向量检索、上传文档和重排序时：

```powershell
cd backend
.venv\Scripts\python.exe -m pip install -r requirements-rag.txt
.venv\Scripts\python.exe scripts\ingest_medical_docs.py
```

首次安装会下载 PyTorch、Chroma 和本地 BGE 模型，体积较大。`DASHSCOPE_API_KEY` 是可选项；未配置时按混合分数排序。

## 核心 API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/health/ping` | 前端就绪检查 |
| `POST` | `/health/consult` | 多 Agent 就诊准备 |
| `POST` | `/risk/detect` | 单独测试规则分诊 |
| `POST` | `/department/recommend` | 单独测试科室规则 |
| `POST` | `/api/knowledge/search` | 增强知识库检索 |
| `POST` | `/api/knowledge/upload` | 上传 PDF/DOCX/TXT/MD |

核心响应除原有建议外，还包含：

- `evidence`：实际检索到的资料与摘录
- `agent_trace`：每位专员的工作摘要和复核状态
- `quality`：证据覆盖与已知限制
- `follow_up_questions`：下一轮最值得补充的信息

## 测试

```powershell
cd backend
.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run build
```

测试覆盖否定症状、胸痛伴呼吸困难、突发剧烈头痛、长期症状、科室推荐和完整 API 协作链路。

## 目录

```text
MediPrepAgent/
├─ backend/
│  ├─ app/agents/          # 多 Agent 协作与专员实现
│  ├─ app/api/             # FastAPI 路由与前端托管
│  ├─ app/rag/             # 可选混合检索
│  ├─ app/services/        # 风险、科室、上下文服务
│  ├─ data/medical_guides/ # 内置医学资料
│  └─ tests/
└─ frontend/
   ├─ src/                 # React 工作台
   └─ dist/                # 生产构建，由 FastAPI 托管
```
