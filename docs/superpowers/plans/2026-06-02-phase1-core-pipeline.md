# Phase 1: 核心链路 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建最小可行产品——用户能上传 PDF/Markdown 文档，通过自适应 Agent 进行 RAG 查询，获得带引文的答案。

**Architecture:** 模块化 FastAPI 单体，LangGraph 编排的 6 节点 Agent 状态机，Milvus 向量检索，PostgreSQL 主存储，本地文件摄入（语义路径）。

**Tech Stack:** Python 3.12+, FastAPI, LangGraph, LangChain, Pydantic v2, PostgreSQL 15+ (pgvector), Milvus v2.4 (pymilvus), Redis 7, ARQ, Alembic, pytest

**Spec:** `docs/superpowers/specs/2026-06-02-adaptive-agent-rag-design.md`

---

## Phase 1 文件结构总览

```
AgentRAGProject/
├── pyproject.toml                         # 项目配置 + 依赖
├── Dockerfile                             # FastAPI 镜像
├── docker-compose.yml                     # PG + Milvus + Redis + FastAPI + ARQ
├── .env.example                           # 环境变量模板
├── alembic.ini                            # 数据库迁移配置
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_initial.py                 # 初始 schema
├── app/
│   ├── __init__.py
│   ├── main.py                            # FastAPI 入口 + CORS + 生命周期
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                      # pydantic-settings
│   │   ├── di.py                          # 依赖注入容器
│   │   ├── events.py                      # startup/shutdown 事件
│   │   └── security.py                    # JWT/bcrypt/API key 工具
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── base.py                        # SQLAlchemy Base + 通用字段
│   │   ├── user.py
│   │   ├── collection.py
│   │   ├── document.py
│   │   └── ingest_job.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                        # get_db, get_current_user
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py                  # 聚合所有子路由
│   │       ├── auth.py
│   │       ├── collections.py
│   │       ├── documents.py
│   │       ├── ingestion.py
│   │       └── queries.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── document_service.py
│   │   ├── collection_service.py
│   │   ├── rag_service.py                 # RAG 查询入口
│   │   └── agent_service.py               # LangGraph 调用包装
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── state.py                       # AgentState TypedDict
│   │   ├── graph.py                       # build_graph() + should_continue()
│   │   ├── nodes.py                       # SYNTHESIZE + 公共逻辑
│   │   ├── understander.py
│   │   ├── router.py
│   │   ├── executor.py
│   │   ├── reflector.py
│   │   └── verifier.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                    # BaseLLM 抽象
│   │   │   ├── openai.py
│   │   │   └── ollama.py
│   │   ├── embedding/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                    # BaseEmbedding 抽象
│   │   │   └── openai_embed.py
│   │   ├── vector_store/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                    # BaseVectorStore 抽象
│   │   │   └── milvus.py
│   │   ├── document_loader/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                    # BaseLoader 抽象
│   │   │   ├── pdf.py
│   │   │   └── markdown.py
│   │   └── chunker/
│   │       ├── __init__.py
│   │       ├── base.py                    # BaseChunker 抽象
│   │       └── recursive.py
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── pipeline.py                    # Parse→Chunk→Embed→Write
│   │   ├── sources/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   └── local.py
│   │   ├── parsers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── pdf.py
│   │   │   └── markdown.py
│   │   └── semantic_path/
│   │       ├── __init__.py
│   │       ├── chunker.py
│   │       ├── embedder.py
│   │       └── milvus_writer.py
│   └── workers/
│       ├── __init__.py
│       ├── ingest.py                      # ARQ ingest worker
│       └── main.py                        # ARQ WorkerSettings
├── tests/
│   ├── conftest.py                        # pytest fixtures
│   └── unit/
│       ├── adapters/
│       │   └── test_chunker.py
│       └── agents/
│           ├── test_router.py
│           ├── test_verifier.py
│           └── test_reflector.py
```

---


## Week 1 Tasks 4-6: Adapters + Auth

### Task 4: LLM Adapter

**Files:** app/adapters/llm/__init__.py, base.py, openai.py, ollama.py

- [ ] **Step 1:** Create `app/adapters/llm/base.py` — BaseLLM ABC with `agenerate(prompt, system_prompt)`, `astream()`, `agenerate_structured(prompt, output_schema)`
- [ ] **Step 2:** Create `app/adapters/llm/openai.py` — OpenAILLM using `openai.AsyncOpenAI`, implements all 3 methods
- [ ] **Step 3:** Create `app/adapters/llm/ollama.py` — OllamaLLM using `langchain_ollama.ChatOllama`
- [ ] **Step 4:** **Test:** `python -c "from app.adapters.llm.base import BaseLLM; print('OK')"`
- [ ] **Step 5:** Commit

### Task 5: Embedding + VectorStore + Loader + Chunker Adapters

**Files:** app/adapters/embedding/, vector_store/, document_loader/, chunker/

- [ ] **Step 1:** Create `embedding/base.py` (BaseEmbedding ABC), `embedding/openai_embed.py` (OpenAIEmbedding)
- [ ] **Step 2:** Create `vector_store/base.py` (BaseVectorStore ABC + SearchResult dataclass), `vector_store/milvus.py` (MilvusStore with pymilvus)
- [ ] **Step 3:** Create `document_loader/base.py` (ParsedDocument dataclass + BaseLoader), `loader/pdf.py`, `loader/markdown.py`
- [ ] **Step 4:** Create `chunker/base.py` (BaseChunker ABC), `chunker/recursive.py` (wrapping LangChain RecursiveCharacterTextSplitter)
- [ ] **Step 5:** Commit

### Task 6: Authentication API

**Files:** app/api/deps.py, app/api/v1/auth.py, router.py, update main.py

- [ ] **Step 1:** Create `app/api/deps.py` — `get_current_user` supports JWT token + API Key dual auth via `HTTPBearer`
- [ ] **Step 2:** Create `app/api/v1/auth.py` — POST `/auth/register`, `/auth/login` (returns JWT), `/auth/api-key` (returns raw key once)
- [ ] **Step 3:** Create `app/api/v1/router.py` — aggregates all sub-routers under `/api/v1`
- [ ] **Step 4:** Update `app/main.py` — register `v1_router`
- [ ] **Step 5:** **Test:** curl register, login, get token, curl api-key
- [ ] **Step 6:** Commit


## Week 2: Ingestion Pipeline + Knowledge Base APIs

### Task 7: Document Ingestion Pipeline

**Files:** app/ingestion/ (all submodules)

- [ ] **Step 1:** Create `ingestion/sources/base.py` + `local.py` (LocalSource: list files, read content)
- [ ] **Step 2:** Create `ingestion/semantic_path/chunker.py`, `embedder.py`, `milvus_writer.py`
- [ ] **Step 3:** Create `ingestion/pipeline.py` — `run_ingest_pipeline()`: for each file → parse → chunk → embed → write Milvus → update doc+job status in PG
- [ ] **Step 4:** **Test:** run pipeline manually with a test PDF, verify Milvus has vectors, PG doc status=ready
- [ ] **Step 5:** Commit

### Task 8: ARQ Worker Setup

**Files:** app/workers/__init__.py, main.py, ingest.py

- [ ] **Step 1:** Create `workers/main.py` — `WorkerSettings` with Redis DSN, `functions=[start_ingest_job]`, `max_jobs=10`, `job_timeout=3600`
- [ ] **Step 2:** Create `workers/ingest.py` — `start_ingest_job` ARQ task wrapping `run_ingest_pipeline`, `enqueue_ingest` helper for API
- [ ] **Step 3:** Test: `arq app.workers.main.WorkerSettings` starts without error
- [ ] **Step 4:** Commit

### Task 9: Collection + Document + Ingestion APIs

**Files:** app/services/collection_service.py, document_service.py, app/api/v1/collections.py, documents.py, ingestion.py

- [ ] **Step 1:** Create `services/collection_service.py` — create, list, get, delete functions
- [ ] **Step 2:** Create `services/document_service.py` — list_by_collection, get, delete
- [ ] **Step 3:** Create `api/v1/collections.py` — POST/GET/DELETE /collections
- [ ] **Step 4:** Create `api/v1/documents.py` — GET/DELETE /collections/{id}/documents/{did}
- [ ] **Step 5:** Create `api/v1/ingestion.py` — POST /ingest/local (save files, create IngestJob, enqueue ARQ), GET /ingest/{job_id}
- [ ] **Step 6:** Update `router.py` to include all new routers
- [ ] **Step 7:** **Integration test:** create collection → upload PDF → poll job status → verify document ready
- [ ] **Step 8:** Commit


## Week 3: Agent Core + RAG Query API

### Task 10: AgentState Definition

**Files:** app/agents/__init__.py, state.py

- [ ] **Step 1:** Create `agents/state.py` — full `AgentState` TypedDict with ALL fields from spec section 3.3
- [ ] **Step 2:** Include `SubTask`, `RetrievedChunk`, `VerifiedClaim`, `Citation` typed dicts
- [ ] **Step 3:** **Test:** `python -c "from app.agents.state import AgentState"`
- [ ] **Step 4:** Commit

### Task 11: Agent Nodes Part 1 (Understand, Route, Execute)

**Files:** app/agents/understander.py, router.py, executor.py

- [ ] **Step 1:** Create `understander.py` — UNDERSTAND node
  - Prompt: "Analyze intent. Decompose into sub-tasks. Output JSON: {intent, rewritten_query, sub_tasks: [{id, description, intent, depends_on}]}"
  - Phase 1 stub: skip experience memory (returns empty)
  - Parse LLM structured output into `AgentState.sub_tasks`

- [ ] **Step 2:** Create `router.py` — ROUTE node
  - Phase 1 hardcode: all routes = "milvus" (no KG/ES yet)
  - Populate `AgentState.routes: {subtask_id: "milvus"}`

- [ ] **Step 3:** Create `executor.py` — EXECUTE node
  - For each sub-task: generate 3 query variant strings via LLM
  - Call `MilvusStore.search()` with each variant (embed query first)
  - Context expansion: for top hits, fetch neighbor chunks (index +/- 1)
  - Merge results, deduplicate by `chunk_id`, sort by score desc
  - Populate `AgentState.retrieved`

- [ ] **Step 4:** **Unit tests** with mock LLM + mock Milvus for each node
- [ ] **Step 5:** Commit

### Task 12: Agent Nodes Part 2 (Reflect, Verify, Synthesize)

**Files:** app/agents/reflector.py, verifier.py, nodes.py

- [ ] **Step 1:** Create `reflector.py` — REFLECT node
  - Generate `draft_answer` from retrieved chunks via LLM
  - Critic prompt: "Check completeness. Is every aspect of the query answered? Missing info? Score 0-1."
  - Parse structured output: {reflection_notes, missing_info, quality_score}
  - Set `need_another_round = quality_score < 0.7`

- [ ] **Step 2:** Create `verifier.py` — VERIFY node
  - Split `draft_answer` into individual claims (by sentence boundary)
  - For each claim: LLM judges "which retrieved chunk supports this claim?"
  - Each claim gets status: verified (has chunk_id), unverified (no source), contradicted (conflicting sources)
  - `need_supplement = verified_ratio < 0.5`

- [ ] **Step 3:** Create `nodes.py` — SYNTHESIZE node with hard constraints
  - System prompt: "1. ONLY use retrieved content. 2. Cite [source: chunk_id] per sentence. 3. Mark uncertainty. 4. Say 'I cannot answer' if no results."
  - Generate `final_answer`, populate `citations`, `uncertainty_flags`

- [ ] **Step 4:** **Unit tests** for each node
- [ ] **Step 5:** Commit

### Task 13: LangGraph State Machine Assembly

**Files:** app/agents/graph.py, app/services/agent_service.py, rag_service.py

- [ ] **Step 1:** Create `agents/graph.py`
  - `build_graph()`: instantiate StateGraph, add 6 nodes, set edges
  - STANDARD FLOW: UNDERSTAND → ROUTE → EXECUTE → REFLECT
  - REFLECT conditional: quality<0.7 → ROUTE, else → VERIFY
  - VERIFY conditional: need_supplement → ROUTE, else → SYNTHESIZE
  - `should_continue()` function: max_iterations cap, quality threshold, no-improvement detection

- [ ] **Step 2:** Create `services/agent_service.py`
  - `AgentService.run(query, collection_ids, session_id, options)`:
    - Initialize `AgentState` from inputs
    - Invoke `compiled_graph.ainvoke(initial_state)`
    - Return final state dict with answer + citations + trace

- [ ] **Step 3:** Create `services/rag_service.py`
  - `RAGService.query()`: validate collection access, call AgentService, format response

- [ ] **Step 4:** **Integration test:** run full graph with mock LLM, verify state transitions, check max_iterations enforcement
- [ ] **Step 5:** Commit

### Task 14: Query API + Trace Storage

**Files:** app/api/v1/queries.py, update router.py, update services

- [ ] **Step 1:** Create `queries.py` with Pydantic models:
  - `QueryRequest(query, collection_ids, session_id, options)`
  - `QueryResponse(answer, citations, agent_trace, uncertainty_flags)`
  - `QueryOptions(max_iterations, quality_threshold, enable_web_search, response_style)`

- [ ] **Step 2:** POST `/api/v1/query` — call `rag_service.query()`, save `query_trace` row, return `QueryResponse`

- [ ] **Step 3:** POST `/api/v1/query/stream` — SSE endpoint:
  - `event: status` for each phase, `event: chunk` for incremental text, `event: done` at end

- [ ] **Step 4:** GET `/api/v1/query/{trace_id}/trace` — return full `agent_graph` JSON from `query_traces` table

- [ ] **Step 5:** Save `query_traces` after each query: model_used, total_tokens, estimated_cost, agent_graph JSON with iterations

- [ ] **Step 6:** Commit

### Task 15: Anti-Hallucination Hardening

**Files:** Update app/agents/verifier.py, nodes.py

- [ ] **Step 1:** Implement SYNTHESIZE hard constraint prompt (4 rules in spec section 6)
- [ ] **Step 2:** Implement sentence-level claim extraction (split on `.` `。` `!` `?`)
- [ ] **Step 3:** Implement evidence matching: LLM pairwise judgment "does chunk X support claim Y?"
- [ ] **Step 4:** Implement contradiction detection: if claim A and claim B from different chunks contradict each other
- [ ] **Step 5:** **Test:** provide chunks about topic A, query about topic B → verify "I cannot answer based on available documents"
- [ ] **Step 6:** Commit

### Task 16: End-to-End Integration Tests

**Files:** tests/conftest.py, tests/e2e/test_user_journey.py

- [ ] **Step 1:** Create `tests/conftest.py` async fixtures:
  - `test_db`: SQLite in-memory via aiosqlite + SQLAlchemy async engine
  - `test_milvus`: mock MilvusStore with in-memory dict
  - `test_client`: httpx.AsyncClient app fixture

- [ ] **Step 2:** User journey test
  - Register user → login → create collection → upload test PDF → wait ingest → POST /query → verify answer + citations
  - POST /query for missing topic → verify "cannot answer" with uncertainty flag

- [ ] **Step 3:** Agent multi-round test
  - Comparison query → verify `agent_trace.iterations >= 1`
  - Verify `agent_trace.quality_score > 0.5`

- [ ] **Step 4:** Run: `pytest tests/ -v` — all pass
- [ ] **Step 5:** Commit

### Task 17: Polish + Smoke Test

- [ ] **Step 1:** Update health check to verify PG + Milvus + Redis connectivity
- [ ] **Step 2:** Add request_id middleware, timing log middleware
- [ ] **Step 3:** `docker compose up -d` full smoke test: health → register → upload → query
- [ ] **Step 4:** Final commit


## Tasks Summary (17 tasks)

| # | Area | Key Deliverable |
|---|------|----------------|
| 1 | Scaffold | pyproject.toml, Docker Compose, .env.example |
| 2 | Core | config.py, security.py, main.py, health check |
| 3 | Domain | 5 SQLAlchemy models, Alembic migration, DI |
| 4 | Adapters | LLM adapter (OpenAI + Ollama) |
| 5 | Adapters | Embedding, VectorStore, Loader, Chunker |
| 6 | Auth | Register, login, API key endpoints |
| 7 | Ingestion | Full pipeline: parse → chunk → embed → write |
| 8 | Workers | ARQ config + ingest task |
| 9 | API | Collection, Document, Ingestion endpoints |
| 10 | Agent | AgentState TypedDict definition |
| 11 | Agent | UNDERSTAND, ROUTE, EXECUTE nodes |
| 12 | Agent | REFLECT, VERIFY, SYNTHESIZE nodes |
| 13 | Agent | LangGraph assembly + AgentService + RAGService |
| 14 | API | /query, /query/stream, /query/{id}/trace |
| 15 | Quality | Anti-hallucination constraints hardened |
| 16 | Tests | E2E user journey + agent multi-round |
| 17 | Polish | Health check, middleware, smoke test |
