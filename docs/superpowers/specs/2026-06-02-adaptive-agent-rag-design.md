# 自适应多智能体 RAG 系统 — 设计文档

> 日期: 2026-06-02
> 状态: 已确认
> 项目: AgentRAGProject

---

## 1. 概述

### 1.1 项目定位

一个**通用 RAG 基础设施平台**，核心特征是**自适应多智能体协同**：
- 根据查询难度自动选择检索策略
- 从用户反馈中持续学习优化
- 适配不同领域/文档类型，自动切换模型和参数
- 支持意图路由（Milvus 向量检索 / Neo4j 知识图谱 / Elasticsearch 全文检索）
- 多轮补充检索 + 反思机制 + 多智能体协同
- 思维链做任务分工，理解智能体 + 执行智能体各司其职
- Memory 模块总结历史对话、反思纠错

### 1.2 技术栈总览

| 层 | 技术 |
|---|---|
| Web 框架 | FastAPI + Pydantic v2 |
| Agent 编排 | LangGraph + LangChain |
| 异步任务 | ARQ (基于 Redis) |
| 数据库 | PostgreSQL 15+ (含 pgvector) |
| 向量库 | Milvus |
| 知识图谱 | Neo4j |
| 全文检索 | Elasticsearch + IK 分词 |
| 缓存/会话 | Redis |
| 对象存储 | MinIO (生产) / 本地文件系统 (MVP) |
| 配置管理 | pydantic-settings + .env |
| 日志 | structlog |
| 监控 | Prometheus + Grafana (生产) |
| 前端 | React + TypeScript + Vite + shadcn/ui |
| 容器化 | Docker Compose (开发) → K8s (生产) |

---

## 2. 系统架构

### 2.1 整体架构图

```
┌──────────────────────────────────────────────────────────┐
│                    FastAPI Server                        │
│  ┌────────┐  ┌─────────┐  ┌─────────┐                   │
│  │REST API│  │Admin UI │  │ User UI │                   │
│  └───┬────┘  └────┬────┘  └────┬────┘                   │
│      │            │            │                         │
│  ┌───┴────────────┴────────────┴────────────────────┐    │
│  │              Service Layer                        │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐          │    │
│  │  │DocService│ │RAGService│ │AgentSvc  │          │    │
│  │  └──────────┘ └──────────┘ └──────────┘          │    │
│  └──────────────────────┬───────────────────────────┘    │
│                         │                                │
│  ┌──────────────────────┴───────────────────────────┐    │
│  │                  Core Layer                       │    │
│  │  ┌────────┐ ┌────────┐ ┌──────────┐ ┌─────────┐  │    │
│  │  │Agents  │ │Memory  │ │  Tools   │ │Adapters │  │    │
│  │  │        │ │        │ │          │ │         │  │    │
│  │  │Orchest-│ │Working │ │Milvus    │ │LLM      │  │    │
│  │  │rator   │ │Short   │ │KG Query  │ │Embedding│  │    │
│  │  │Underst-│ │Long    │ │Keyword   │ │VectorDB  │  │    │
│  │  │ander   │ │        │ │WebSearch │ │DocLoader │  │    │
│  │  │Executor│ │        │ │          │ │Chunker   │  │    │
│  │  │Reflect-│ │        │ │          │ │KG Adapter│  │    │
│  │  │or      │ │        │ │          │ │         │  │    │
│  │  │Router  │ │        │ │          │ │         │  │    │
│  │  └────────┘ └────────┘ └──────────┘ └─────────┘  │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                │
│  ┌──────────────────────┴───────────────────────────┐    │
│  │              Ingestion Layer                      │    │
│  │  Sources → Parse → Fork → 3 Paths → Index       │    │
│  └───────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼────┐    ┌───────▼──────┐    ┌──────▼──────┐
   │ Milvus  │    │    Neo4j     │    │Elasticsearch│
   │向量检索  │    │   知识图谱   │    │  全文检索    │
   └─────────┘    └──────────────┘    └─────────────┘
        │                  │                  │
   ┌────▼────┐    ┌───────▼──────┐    ┌──────▼──────┐
   │PostgreSQL│   │    Redis     │    │   MinIO     │
   │(主存储)  │   │  (缓存/会话) │    │ (文件存储)   │
   └──────────┘   └──────────────┘    └─────────────┘
```

### 2.2 模块职责

| 模块 | 职责 | 关键文件 |
|------|------|----------|
| `app/agents/` | 多智能体核心：Orchestrator, Understander, Router, Executor, Reflector, Verifier | `graph.py`, `nodes.py` |
| `app/memory/` | 三层记忆：Working(会话内) / Short-term(Redis) / Long-term(PG+Milvus) | `conversation.py`, `long_term.py` |
| `app/tools/` | Agent 可调用的工具集（向量检索、KG查询、关键词搜索、Web搜索） | `vector_search.py`, `kg_query.py` |
| `app/adapters/` | 外部依赖抽象层（LLM, Embedding, 向量库, 文档加载器, 分块器, KG） | `llm/`, `embedding/`, `vector_store/` |
| `app/ingestion/` | 统一摄入层：三种来源 → 三路处理路径 | `pipeline.py`, `sources/` |
| `app/services/` | 业务编排服务 | `rag_service.py`, `document_service.py` |
| `app/api/` | REST API 端点 | `v1/` |

### 2.3 项目目录结构

```
AgentRAGProject/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/                     # REST API
│   │   ├── deps.py
│   │   └── v1/
│   │       ├── auth.py
│   │       ├── sessions.py
│   │       ├── collections.py
│   │       ├── documents.py
│   │       ├── ingestion.py
│   │       ├── sources.py
│   │       ├── queries.py
│   │       ├── feedbacks.py
│   │       ├── memories.py
│   │       └── admin.py
│   ├── agents/                  # 多智能体
│   │   ├── base.py
│   │   ├── state.py
│   │   ├── graph.py
│   │   ├── nodes.py
│   │   ├── orchestrator.py
│   │   ├── understander.py
│   │   ├── router.py
│   │   ├── executor.py
│   │   ├── reflector.py
│   │   └── verifier.py
│   ├── memory/                  # 记忆模块
│   │   ├── base.py
│   │   ├── working.py
│   │   ├── conversation.py
│   │   ├── long_term.py
│   │   └── reflection.py
│   ├── tools/                   # Agent 工具集
│   │   ├── base.py
│   │   ├── vector_search.py
│   │   ├── kg_query.py
│   │   ├── keyword_search.py
│   │   └── web_search.py
│   ├── adapters/                # 适配器层
│   │   ├── llm/
│   │   │   ├── base.py
│   │   │   ├── openai.py
│   │   │   ├── anthropic.py
│   │   │   └── ollama.py
│   │   ├── embedding/
│   │   │   ├── base.py
│   │   │   ├── openai_embed.py
│   │   │   └── local_embed.py
│   │   ├── vector_store/
│   │   │   ├── base.py
│   │   │   └── milvus.py
│   │   ├── document_loader/
│   │   │   ├── base.py
│   │   │   ├── pdf.py
│   │   │   ├── markdown.py
│   │   │   ├── code.py
│   │   │   └── html.py
│   │   ├── chunker/
│   │   │   ├── base.py
│   │   │   ├── recursive.py
│   │   │   ├── semantic.py
│   │   │   └── hierarchical.py
│   │   └── kg/
│   │       ├── base.py
│   │       └── neo4j.py
│   ├── ingestion/               # 统一摄入层
│   │   ├── pipeline.py
│   │   ├── sources/
│   │   │   ├── base.py
│   │   │   ├── local.py
│   │   │   ├── web.py
│   │   │   └── database.py
│   │   ├── parsers/
│   │   │   ├── base.py
│   │   │   ├── pdf.py
│   │   │   ├── markdown.py
│   │   │   ├── code.py
│   │   │   ├── csv_json.py
│   │   │   └── html.py
│   │   ├── semantic_path/
│   │   │   ├── chunker.py
│   │   │   ├── embedder.py
│   │   │   └── milvus_writer.py
│   │   ├── graph_path/
│   │   │   ├── entity_extractor.py
│   │   │   ├── relation_extractor.py
│   │   │   └── neo4j_writer.py
│   │   └── keyword_path/
│   │       ├── structure_keeper.py
│   │       └── es_writer.py
│   ├── services/                # 业务层
│   │   ├── document_service.py
│   │   ├── collection_service.py
│   │   ├── rag_service.py
│   │   ├── agent_service.py
│   │   ├── feedback_service.py
│   │   └── security_service.py
│   ├── domain/                  # 数据模型（纯 Python，无框架依赖）
│   │   ├── document.py
│   │   ├── collection.py
│   │   ├── query.py
│   │   ├── feedback.py
│   │   └── memory.py
│   ├── core/                    # 基础设施
│   │   ├── config.py
│   │   ├── di.py
│   │   ├── events.py
│   │   ├── security.py
│   │   └── telemetry.py
│   └── workers/                 # 后台任务
│       ├── ingest.py
│       ├── kg_build.py
│       ├── memory_consolidate.py
│       └── repair.py
├── frontend/
│   ├── admin/                   # 管理后台
│   └── user/                    # 用户 Chat UI
├── tests/
│   ├── unit/
│   │   ├── agents/
│   │   ├── memory/
│   │   ├── tools/
│   │   ├── adapters/
│   │   └── ingestion/
│   ├── integration/
│   │   ├── test_agent_graph.py
│   │   ├── test_ingestion_pipeline.py
│   │   └── test_api.py
│   └── e2e/
│       ├── test_user_journey.py
│       └── test_degradation.py
├── docs/
│   └── superpowers/
│       └── specs/
├── pyproject.toml
├── Dockerfile
└── docker-compose.yml
```

---

## 3. 多智能体协同设计

### 3.1 智能体角色

```
┌──────────────────────────────────────────────────────────────────┐
│                       智能体协同流程                               │
├────────────┬─────────────────────────────────────────────────────┤
│            │                                                     │
│ Orchestrator│ 接收查询 → 启动 Understand → 收集结果 → 启动        │
│ (编排器)    │ Execute → 触发 Reflect → 决策是否继续/返回          │
│            │                                                     │
│ Understand │ 意图识别 → 查询改写 → 任务分解(CoT) → 输出执行计划   │
│ (理解器)    │ "这个查询需要先查定义,再找例子,最后做对比"           │
│            │                                                     │
│ Router     │ 分析子任务类型 → 选择检索路径                         │
│ (路由器)    │ 事实查询→Milvus | 关系查询→KG | 精确匹配→关键词      │
│            │                                                     │
│ Execute    │ 多查询改写 → 多路并行检索 → 上下文扩展 → 重排序       │
│ (执行器)    │ 按计划调用 Router → 收集检索结果                     │
│            │                                                     │
│ Reflect    │ 检查答案完整性 → 发现缺口 → 请求补充检索               │
│ (反思器)    │ "缺少对比维度" → 触发新一轮 Execute                  │
│            │                                                     │
│ Verify     │ 逐句溯源 → 矛盾检测 → 引文标注 → 未验证声明处理       │
│ (验证器)    │ 每个事实声明必须有检索来源支撑                        │
│            │                                                     │
│ Memory     │ 压缩历史对话 → 提取关键事实 → 纠错学习                 │
│ (记忆)     │ 知识记忆/经验记忆/画像记忆                             │
│            │                                                     │
└────────────┴─────────────────────────────────────────────────────┘
```

### 3.2 LangGraph 状态机

```
                    ┌──────────┐
                    │  START   │
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │UNDERSTAND│  意图 + CoT分解
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │  ROUTE   │  意图路由（Milvus/KG/ES/Web）
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │ EXECUTE  │  多查询改写 + 多路并行 + 上下文扩展 + 重排序
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │ REFLECT  │  完整性检查（是否遗漏知识点）
                    └────┬─────┘
                         │
                   ┌─────┴─────┐
                   │ 信息完整？  │
                   └─────┬─────┘
                     │       │
                    NO      YES
                     │       │
              ┌──────▼──┐    │
              │ 补充计划  │    │
              │(回ROUTE) │    │
              └──────────┘    │
                              │
                    ┌─────────▼──┐
                    │  VERIFY    │  逐句溯源 + 矛盾检测 + 引文标注
                    └─────────┬──┘
                              │
                   ┌──────────┴──────┐
                   │ 所有声明有来源？  │
                   └──────────┬──────┘
                        │         │
                       NO        YES
                        │         │
                 ┌──────▼──┐      │
                 │ 补查缺口  │      │
                 │(回EXECUTE)│     │
                 └──────────┘      │
                                   │
                         ┌─────────▼──┐
                         │ SYNTHESIZE │  禁编造 + 引文强制 + 不确定性标注
                         └─────────┬──┘
                                   │
                         ┌─────────▼──┐
                         │   MEMORY   │  记忆更新
                         └─────────┬──┘
                                   │
                              ┌────▼───┐
                              │  END   │
                              └────────┘
```

### 3.3 状态定义

```python
class SubTask(TypedDict):
    id: str
    description: str
    intent: Literal["fact", "relation", "comparison", "reasoning"]
    route: Literal["milvus", "kg", "keyword", "web", "hybrid"]
    depends_on: List[str]
    status: Literal["pending", "running", "done", "failed"]

class AgentState(TypedDict):
    query: str
    conversation_history: List[dict]
    
    # Understand 产出
    intent: str
    rewritten_query: str
    sub_tasks: List[SubTask]
    
    # Execute 产出
    retrieved_chunks: List[dict]
    kg_results: List[dict]
    keyword_hits: List[dict]
    
    # Reflect 产出
    reflection_notes: str
    missing_info: List[str]
    quality_score: float
    need_another_round: bool
    
    # Verify 产出
    verified_claims: List[dict]
    
    # 循环控制
    iteration: int
    max_iterations: int
    
    # 最终产出
    final_answer: str
```

### 3.4 防死循环策略

```python
def should_continue(state: AgentState):
    # 策略1: 硬上限
    if state["iteration"] >= state["max_iterations"]:
        return "maxed"
    # 策略2: 质量达标
    if state["quality_score"] >= 0.7:
        return "done"
    # 策略3: 连续两轮无改善
    if state.get("prev_score") and state["quality_score"] <= state["prev_score"]:
        return "done"
    state["prev_score"] = state["quality_score"]
    return "retry"
```

### 3.5 各节点 Prompt 策略

| 节点 | Prompt 核心逻辑 |
|------|----------------|
| UNDERSTAND | 分析查询意图，考虑对话历史。将复杂查询分解为可独立检索的子任务，标注意图类型和依赖关系 |
| ROUTE | 为每个子任务选最佳检索路径：语义理解→milvus，实体关系→kg，精确匹配→keyword，最新信息→web，复杂需求→hybrid |
| EXECUTE | 多查询改写生成变体 → 多路并行检索 → 上下文窗口扩展 → Cross-encoder 重排序 |
| REFLECT | 批判者角色：完整性检查、事实支撑检查、矛盾检测、打分0-1。分数<0.7触发补充检索 |
| VERIFY | 逐句拆解声明 → 逐条溯源 → 矛盾检测 → 未验证声明触发补充 → 输出带引文标记的答案 |
| SYNTHESIZE | 硬约束：禁编造、引文强制、不确定性标注、拒绝回答（无结果时直接说不知道） |
| MEMORY | 提取关键结论→知识记忆，检索策略效果→经验记忆，用户偏好信号→画像记忆 |

---

## 4. 统一多源摄入层

### 4.1 三种摄入源

| 来源 | 输入方式 | 处理逻辑 |
|------|---------|---------|
| 📁 LOCAL | 上传文件 / 批量导入目录 / API 传入文本 | 自动检测文件类型选择 parser |
| 🌐 WEB | URL 列表 / 搜索关键词 / 整站爬取 | 爬取+渲染+去噪+正文提取 |
| 🗄️ DATABASE | PG/MySQL/Mongo 连接串 / REST API | 表结构→文档映射 / 增量同步(CDC) |

### 4.2 摄入管道（Parse 后分叉）

```
Source → [Parse] → [Clean] → Fork:
                               │
                  ┌────────────┼────────────┐
                  │            │            │
                  ▼            ▼            ▼
        ┌──────────────┐ ┌──────────┐ ┌──────────────┐
        │ 🧠 语义路径   │ │ 🕸️ 图谱  │ │ 📄 关键词路径 │
        │ → Milvus     │ │ → Neo4j  │ │ → ES         │
        ├──────────────┤ ├──────────┤ ├──────────────┤
        │ 智能分块      │ │ 实体抽取  │ │ 结构化保留    │
        │ Embedding    │ │ 关系抽取  │ │ 分词+倒排    │
        │ 写入 Milvus  │ │ 写入Neo4j │ │ 写入 ES      │
        └──────────────┘ └──────────┘ └──────────────┘
```

### 4.3 为什么不能统一分块

| 存储 | 需要分块吗？ | 原因 |
|------|------------|------|
| Milvus | ✅ 需要小粒度智能分块 (512-1024 tokens) | 语义检索靠 chunk embedding，太大语义稀释，太小上下文碎片化 |
| Neo4j | ❌ 完全不需要分块 | 需要的是实体+关系三元组，分块破坏实体关联 |
| Elasticsearch | ❌ 不需要小块，需要文档级或大段 (2000+词) | 倒排索引+BM25，小块降低召回精度，精确匹配需要完整上下文 |

### 4.4 写入一致性策略

三路写入的事务性策略:
1. 先写 PG (documents 表 + status = processing)
2. 并行写 Milvus + Neo4j + ES
3. 汇总结果 → 决定最终 status
   - 全部成功 → ready
   - Milvus 成功但其他失败 → partial (核心检索可用)
   - Milvus 失败 → error
4. 失败路径自动入修复队列

---

## 5. Memory 模块

### 5.1 三层记忆结构

| 层 | 生命周期 | 存储 | 内容 |
|----|---------|------|------|
| Working Memory | 单次查询 | AgentState (不持久化) | 当前消息、检索中间结果、trace |
| Short-term Memory | 多轮对话 | Redis (TTL 24h) | 对话摘要、话题追踪、已确认事实 |
| Long-term Memory | 永久 | PG + Milvus | 知识记忆、经验记忆、画像记忆 |

### 5.2 三种长期记忆

- **知识记忆**: 从对话中提取的关键事实（"A方案用MySQL"），带来源和置信度。下次类似查询直接从记忆命中，更快更准。
- **经验记忆**: 检索策略的效果记录（"宽泛查询直接检索→失败"），指导后续策略选择。让 Agent 从失败中学习。
- **画像记忆**: 用户偏好（语言、风格、领域、术语习惯），影响回答方式。

### 5.3 对话压缩

当消息超过阈值(10条)，LLM 摘要压缩前N条，保留待办事项和用户确认过的事实，压缩掉闲聊和已解决的中间步骤。

### 5.4 反思纠错

用户纠正 → 标记旧事实为已纠正 → 记录更正后事实(confidence=1.0) → 溯源修复 → 经验记忆录入教训

---

## 6. API 设计

完整端点清单（48个）:

### 认证 (3)
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/api-key`

### 会话 (4)
- `POST /api/v1/sessions`
- `GET /api/v1/sessions/{id}`
- `DELETE /api/v1/sessions/{id}`
- `GET /api/v1/sessions/{id}/history`

### 知识库 (7)
- `POST /api/v1/collections`
- `GET /api/v1/collections`
- `DELETE /api/v1/collections/{id}`
- `GET /api/v1/collections/{id}/config`
- `PATCH /api/v1/collections/{id}/config`
- `POST /api/v1/collections/{id}/search`
- `POST /api/v1/collections/{id}/rebuild-index`

### 文档 (7)
- `GET /api/v1/collections/{id}/documents`
- `GET /api/v1/collections/{id}/documents/{did}`
- `DELETE /api/v1/collections/{id}/documents/{did}`
- `POST /api/v1/collections/{id}/documents/{did}/reindex`
- `PATCH /api/v1/collections/{id}/documents/{did}`
- `POST /api/v1/collections/{id}/documents/batch-delete`
- `GET /api/v1/collections/{id}/documents/{did}/chunks`

### 摄入 (5)
- `POST /api/v1/ingest/local`
- `POST /api/v1/ingest/web`
- `POST /api/v1/ingest/database`
- `POST /api/v1/ingest/batch`
- `GET /api/v1/ingest/{job_id}`
- `GET /api/v1/ingest/{job_id}/errors`
- `POST /api/v1/ingest/{job_id}/retry`

### 摄入源配置 (4)
- `POST /api/v1/sources/web`
- `POST /api/v1/sources/database`
- `GET /api/v1/sources`
- `DELETE /api/v1/sources/{id}`

### 查询 (4)
- `POST /api/v1/query`
- `POST /api/v1/query/stream`
- `GET /api/v1/query/{trace_id}/trace`
- `POST /api/v1/query/compare`

### 反馈 (3)
- `POST /api/v1/feedback`
- `GET /api/v1/feedback?trace_id=xxx`
- `GET /api/v1/feedback/stats`

### 记忆 (7)
- `GET /api/v1/memories`
- `POST /api/v1/memories/search`
- `POST /api/v1/memories`
- `PATCH /api/v1/memories/{id}`
- `DELETE /api/v1/memories/{id}`
- `DELETE /api/v1/memories?type=corrected`
- `POST /api/v1/memories/export`

### 管理 (8)
- `GET /api/v1/admin/stats`
- `GET /api/v1/admin/stats/routes`
- `GET /api/v1/admin/logs`
- `GET /api/v1/admin/health`
- `POST /api/v1/admin/export`
- `POST /api/v1/admin/providers/llm`
- `POST /api/v1/admin/providers/embedding`
- `POST /api/v1/admin/providers/vector-store`
- `GET /api/v1/admin/models`
- `GET /api/v1/admin/models/{name}/metrics`
- `GET /api/v1/admin/users/{id}/profile`
- `DELETE /api/v1/admin/users/{id}/profile/{key}`

### 关键 API 设计细节

**查询请求**:
```json
{
  "query": "对比A方案和B方案的扩展性",
  "collection_ids": ["col_tech_docs"],
  "session_id": "sess_abc123",
  "options": {
    "max_iterations": 5,
    "quality_threshold": 0.7,
    "enable_web_search": false,
    "response_style": "concise"
  }
}
```

**查询响应**: 包含 answer、citations、agent_trace、uncertainty_flags

**流式事件 (SSE)**:
- `event: status` — understanding / routing / executing / reflecting / verifying
- `event: chunk` — 文本片段 + 实时引文
- `event: done` — trace_id + iterations + quality_score

**SYNTHESIZE 强制约束**:
1. 禁编造 — 每个事实性陈述必须来自检索结果
2. 引文强制 — 每句话末尾标注来源 `[来源: chunk_id]`
3. 不确定性标注 — 来源矛盾标注分歧，缺乏信息标注"暂未找到"
4. 拒绝回答 — 没有任何相关检索结果时直接说"无法回答"

---

## 7. 数据模型

### 7.1 PostgreSQL (15张表)

| 表 | 关键字段 |
|----|---------|
| users | id, username, email, password_hash, api_key_hash, role, is_active, last_login_at |
| api_keys | id, user_id, name, key_hash, last_used_at, is_active |
| user_quotas | id, user_id, quota_type, limit_value, used_value, period_start, period_end |
| collections | id, owner_id, name, config(JSONB), doc_count, chunk_count, status |
| documents | id, collection_id, title, source_type, source_path, mime_type, content_hash, embedding_model, language, metadata(JSONB), chunk_count, status, error_message |
| ingest_jobs | id, collection_id, user_id, source_type, config_snapshot(JSONB), total/completed/failed_docs, errors(JSONB), status, started_at, completed_at |
| source_configs | id, user_id, source_type, name, config(JSONB), is_active, last_run_at |
| provider_configs | id, user_id, provider_type, provider_name, config_encrypted(BYTEA), is_default, is_active |
| sessions | id, user_id, collection_id, title, summary, message_count, is_active, last_activity_at |
| messages | id, session_id, trace_id, role, content(TEXT), citations(JSONB), token_count |
| query_traces | id, session_id, user_id, collection_ids(JSONB), query(TEXT), answer(TEXT), model_used, total_tokens, estimated_cost, citations(JSONB), agent_graph(JSONB), quality_score, iterations, latency_ms |
| feedbacks | id, trace_id, user_id, rating, feedback_type, comment, correction, resolved_status, admin_notes |
| long_term_memories | id, user_id, type(knowledge/experience/profile), entity, content(JSONB), embedding(vector 1024), confidence, source_trace_id, status, corrected_by |
| system_configs | id, key, value(JSONB), description, updated_by |
| audit_logs | id, user_id, action, resource_type, resource_id, detail(JSONB), ip_address, user_agent |

### 7.2 索引设计

```sql
CREATE INDEX idx_sessions_user ON sessions(user_id, is_active);
CREATE INDEX idx_messages_session ON messages(session_id, created_at);
CREATE INDEX idx_documents_collection ON documents(collection_id, status);
CREATE INDEX idx_query_traces_session ON query_traces(session_id, created_at);
CREATE INDEX idx_query_traces_user ON query_traces(user_id, created_at);
CREATE INDEX idx_feedbacks_trace ON feedbacks(trace_id);
CREATE INDEX idx_memories_user_type ON long_term_memories(user_id, type, status);
CREATE INDEX idx_memories_embedding ON long_term_memories 
  USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_ingest_jobs_collection ON ingest_jobs(collection_id, status);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id, created_at);
CREATE INDEX idx_user_quotas_user ON user_quotas(user_id, quota_type);
```

### 7.3 Milvus (2个Collection)

**col_{id}** (文档 chunk):
```
id(int64), chunk_id(varchar), document_id(varchar), text(varchar),
embedding(float_vector), metadata(json), chunk_index(int32), parent_chunk_id(varchar)
索引: IVF_FLAT / HNSW, 度量: COSINE
```

**memories** (记忆语义搜索):
```
memory_id(varchar), embedding(float_vector), metadata(json)
```

### 7.4 Neo4j 图模型

- **节点**: `(:Document {id, title})`, `(:Entity {id, name, type, aliases})`, `(:Chunk {id, text})`
- **关系**: `HAS_CHUNK`, `REFERENCES`, `MENTIONED_IN`, `RELATED_TO {type}`, `LINKS_TO`

### 7.5 Elasticsearch

索引 `col_{id}`: document_id(keyword), title(text+ik_max_word), content(text+ik_max_word), section_path(keyword), page_number(integer), source_type(keyword), ingested_at(date)

### 7.6 Redis

| Key | Value | TTL |
|-----|-------|-----|
| session:{id}:summary | 压缩对话摘要 | 24h |
| session:{id}:topic | 当前话题 | 24h |
| session:{id}:facts | 已确认事实 JSON | 24h |
| session:{id}:window | 最近10条消息 | 24h |
| user:{id}:profile | 用户画像 JSON | 7d |

---

## 8. 错误处理与安全

### 8.1 错误码体系

| 类别 | HTTP | 示例 |
|------|------|------|
| INVALID_INPUT | 400 | 文件格式不支持 |
| QUOTA_EXCEEDED | 429 | 本月 token 额度用完 |
| AUTHENTICATION | 401 | API Key 无效 |
| AUTHORIZATION | 403 | 无权访问该知识库 |
| NOT_FOUND | 404 | 文档/会话/知识库不存在 |
| CONFLICT | 409 | 同名知识库已存在 |
| PROVIDER_ERROR | 502 | LLM/Embedding 服务不可用 |
| VECTOR_STORE_ERROR | 502 | Milvus 连接失败 |
| INGEST_FAILED | 500 | 文档解析失败 |
| AGENT_LOOP_ERROR | 500 | Agent 达到最大迭代仍无结果 |
| INTERNAL | 500 | 未知内部错误 |

统一响应格式:
```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "文档 doc_xyz 不存在",
    "detail": "可能已被删除或从未成功摄入",
    "request_id": "req_abc123"
  }
}
```

### 8.2 降级策略

| 故障场景 | 降级策略 |
|---------|---------|
| Milvus 超时 | 跳过向量检索，用 ES + KG 继续，Reflect 标注"向量检索未完成" |
| LLM 调用失败 | 重试1次 → 降级到更便宜模型 → 仍失败返回错误+已有结果 |
| Neo4j 不可用 | 跳过知识图谱，只用 Milvus+ES，标注"关系查询不可用" |
| Agent 循环超限 | 停止迭代，返回已有结果，标注"答案可能不完整" |
| VERIFY 大量未验证 | 标记所有未验证声明，降低 confidence 而非阻塞 |
| 全部检索不可用 | 降级到 memory 中已有事实回答，明确告知用户当前无法检索 |

### 8.3 安全防护

- **文件上传**: magic bytes 类型检测 + 大小限制(100MB) + 内容去重(content_hash) + 扫描件检测
- **查询输入**: 长度限制(4000字符) + 注入检测 + 非空校验
- **Token 预算**: 单次查询最大 32000 tokens
- **文件类型白名单**: PDF, TXT, MD, CSV, JSON, DOCX
- **认证**: bcrypt 密码哈希 + API Key SHA-256 哈希

### 8.4 全链路追踪

OpenTelemetry trace 贯穿: FastAPI → LangGraph 各节点(understand/route/execute/reflect/verify/synthesize) → Milvus → Neo4j → ES → LLM

### 8.5 告警

| 告警 | 条件 |
|------|------|
| P1 日费用超预算 | daily_llm_cost > budget * 1.5 |
| P1 暴力破解嫌疑 | auth.failure_rate > 20/min |
| P2 摄入失败率 | ingestion.failure_rate > 10% (5min窗口) |
| P2 查询延迟 | agent.query.latency_p99 > 10s |
| P2 存储预警 | pg.disk_usage > 80% / redis.memory_usage > 80% |
| P3 队列积压 | ingestion.queue_depth > 100 |
| P3 向量库容量 | milvus.collection_size > 50GB |

---

## 9. 测试策略

### 9.1 测试金字塔

| 层 | 数量 | 重点 |
|----|------|------|
| Unit | 50-80 | adapter mock、agent node 状态验证、router 决策、security 边界、chunker/parser 正确性 |
| Integration | 20-30 | Agent 完整流转(Milvus-lite+SQLite+testcontainer)、摄入管道、API+DB |
| E2E | 5-10 | 用户完整旅程、多轮对话、降级场景、反馈闭环 |

### 9.2 关键测试用例

**Router**: 事实查询→Milvus / 关系查询→KG / 精确匹配→keyword / 复杂对比→hybrid

**Verifier**: 全部声明有来源→通过 / 超过一半无来源→触发补充 / 空结果→拒绝回答

**Reflector**: 对比查询缺失维度→触发重试 / 完整答案→通过

**Execute**: 多查询改写生成变体 / 多路并行结果合并 / 上下文扩展取邻块+父块

**降级**: Mock Milvus 不可用→降级到 ES+KG / 全部检索不可用→最简模式

---

## 10. MVP 分阶段计划

### Phase 1: 核心链路 (2-3周)

**目标**: 上传文档 → 智能体 RAG 查询 → 返回带引文的答案

| 周 | 内容 |
|----|------|
| W1 | 项目脚手架 + Docker Compose + PG/Milvus/Redis + 认证 + adapter 层 + 数据模型迁移 |
| W2 | 本地文件摄入(PDF/MD/TXT) + Parse→Chunk→Embed→Write + Milvus 检索 + 知识库/文档管理 API |
| W3 | LangGraph 状态机 + 多查询改写+上下文扩展 + 引文强制+防幻觉 + 查询API/流式/回溯 + 集成测试+E2E |

**交付物**: Docker Compose 一键启动，能上传文档并做智能 RAG 查询

### Phase 2: 完善检索 + 知识图谱 (2-3周)

**目标**: 三路检索全部可用，多智能体协同，Memory 模块

| 周 | 内容 |
|----|------|
| W4 | Neo4j + 实体/关系抽取 + ES + 全文检索 + 三路并行+重排序 + 意图路由器 |
| W5 | 多智能体全量 + 三层Memory + 对话压缩+纠错 + 会话管理 |
| W6 | Web爬取摄入 + DB摄入 + 反馈闭环 + 摄入错误处理+一致性修复 + 集成测试 |

**交付物**: 完整的三路检索 + 多智能体 + 记忆 + 多源摄入

### Phase 3: 前端 + 生产化 (2-3周)

**目标**: 完整全栈应用，可对外提供服务

| 周 | 内容 |
|----|------|
| W7 | Admin UI (知识库/文档/摄入源/系统管理) |
| W8 | User Chat UI (流式/引文/反馈) + 查询回溯可视化 + 监控告警 + 压力测试 |

**交付物**: 完整产品，可部署到生产环境

---

## 11. 关键设计决策记录

| 决策 | 理由 |
|------|------|
| 模块化单体而非微服务 | MVP 快速验证，模块边界清晰可后续拆分 |
| 摄入管道 Parse后三路分叉 | 三种存储对分块需求不同，统一分块会牺牲质量 |
| LangGraph 做编排 | 状态机天然适合 Agent 决策循环，LangChain 生态减少胶水代码 |
| 先向量检索再补 KG 和 ES | MVP 优先跑通核心链路，逐步增加检索能力 |
| 先本地文件摄入再 Web/DB | 降低 MVP 复杂度，后续扩展 |
| Memory 走 PG+Milvus 双写 | 语义搜索走 Milvus，结构化查询走 PG |
| adapter 层抽象所有外部依赖 | 不被单一供应商锁定，方便测试 mock |
| VERIFY 节点独立于 Reflect | 完整性检查和事实核查是不同维度，独立节点更清晰 |
| 错误降级而非阻断 | Agent 循环中单个组件故障不应导致整体不可用 |
| SYNTHESIZE 强制引文 | 从源头防止幻觉，而非事后检测 |