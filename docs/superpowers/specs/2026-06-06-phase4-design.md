# Phase 4: Infrastructure Completion & Hardening

**Date**: 2026-06-06
**Scope**: Wire up all stubbed/no-op components from Phase 1-2, complete the RAG pipeline end-to-end, and fill test coverage gaps.

## Current Gap Analysis

6 critical components have full infrastructure (DB tables, adapters, service classes) but are never wired into the pipeline:

| # | Gap | Root Cause |
|---|-----|-----------|
| 1 | LLM provider hardcoded | All 6 agent nodes + 1 tool do `OpenAILLM()` directly |
| 2 | Memory node is no-op | `memory_node()` returns state unchanged |
| 3 | QueryTrace never persisted | Table + model exist; no INSERT called |
| 4 | Conversation history empty | `conversation_history: []` never loaded from Redis |
| 5 | Trace endpoint stub | `GET /query/{id}/trace` returns hardcoded note |
| 6 | ~60% agent code untested | 4/6 agent nodes + all LLM adapters: 0 tests |

## SP0: LLM Provider Factory

**Why first**: Every agent node hardcodes `OpenAILLM()`. Must decouple before anything else.

**Config additions** (`app/core/config.py`):
```python
llm_provider: Literal["openai", "ollama"] = "openai"
ollama_model: str = "qwen2.5"
ollama_base_url: str = "http://localhost:11434"
```

**New file**: `app/core/llm_factory.py`
- `get_llm() -> BaseLLM` — returns OpenAILLM() or OllamaLLM() based on settings.llm_provider
- Singleton via `@lru_cache()` for performance

**Files to modify** (replace `OpenAILLM()` → `get_llm()`):
- `app/agents/understander.py`
- `app/agents/router.py`
- `app/agents/reflector.py`
- `app/agents/verifier.py`
- `app/agents/nodes.py`
- `app/tools/semantic_search.py`

**Verification**: All 75 existing tests pass (they mock OpenAILLM, factory transparent)

---

## SP1: Memory Node + QueryTrace Persistence

**Memory node** (`app/agents/graph.py`):
- Replace no-op with actual implementation
- After synthesize produces final answer, persist to Redis:
  - Save conversation window (last N messages)
  - Save summary
  - Save topic extraction

**QueryTrace persistence** (`app/services/agent_service.py`):
- After `graph.ainvoke()` returns, build QueryTrace row and INSERT via DB session
- Fields: user_id, session_id, query, answer, model_used, total_tokens, estimated_cost, citations, agent_graph, quality_score, iterations, latency_ms
- AgentService.run() signature: add `db: AsyncSession, user_id: str` params
- RAGService.query() passes db + user_id through

**Design decision**: QueryTrace INSERT lives in AgentService (not memory node) because:
- LangGraph State is TypedDict (JSON-serializable) — cannot hold AsyncSession
- AgentService already has access to both graph result and DB session

---

## SP2: Conversation History Injection

**AgentService.run()** — before building initial_state, load context from Redis:
```python
if session_id:
    context = await ConversationMemory.get_context(session_id)
    initial_state["conversation_history"] = context["window"]
```

**Verification**: Multi-turn conversation — second query's `conversation_history` is populated

---

## SP3: Trace API + Web Search Tool

### Trace API
- `GET /query/{trace_id}/trace` — read from `query_traces` table, return full trace

### Web Search Tool
- New file: `app/tools/web_search.py`
- Uses `httpx` for HTTP GET to a configurable search API
- Registers in ToolRegistry as `web_search`
- Router fallback rules: add `"web"` intent → `["web_search"]`
- QueryOptions.enable_web_search gates whether it's included in routing

---

## SP4: Test Coverage

Target: 80%+ coverage on previously untested code.

| Test file | Covers |
|-----------|--------|
| `tests/unit/agents/test_understander.py` | understand_node with mocked LLM |
| `tests/unit/agents/test_reflector.py` | reflector_node with mocked LLM |
| `tests/unit/agents/test_verifier.py` | verifier_node with mocked LLM |
| `tests/unit/agents/test_synthesizer.py` | synthesize_node with mocked LLM |
| `tests/unit/adapters/test_ollama.py` | OllamaLLM adapter |
| `tests/unit/core/test_llm_factory.py` | get_llm() returns correct provider |
| `tests/unit/tools/test_web_search.py` | WebSearchTool |

---

## File Change Summary

| SP | New Files | Modified Files |
|----|-----------|---------------|
| SP0 | `app/core/llm_factory.py` | `config.py`, `understander.py`, `router.py`, `reflector.py`, `verifier.py`, `nodes.py`, `semantic_search.py` |
| SP1 | — | `graph.py`, `agent_service.py`, `rag_service.py` |
| SP2 | — | `agent_service.py` |
| SP3 | `app/tools/web_search.py` | `queries.py`, `router.py`, `tools/__init__.py` |
| SP4 | 7 test files | — |

## Not In Scope

- Neo4j vector embedding search
- Elasticsearch structured filter pushdown
- Ollama native JSON mode
- Admin UI changes