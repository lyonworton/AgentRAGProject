# Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up 6 stubbed/no-op components from Phase 1-2: LLM factory, memory node, QueryTrace persistence, conversation history, trace API, web search. Fill test coverage gaps to 80%+.

**Architecture:** SP0 creates `app/core/llm_factory.py` with `get_llm()` singleton, replaces 7 hardcoded `OpenAILLM()` calls. SP1 replaces the no-op `memory_node` with Redis persistence + adds QueryTrace INSERT in AgentService. SP2 injects conversation history from Redis into AgentState. SP3 implements trace GET endpoint + DuckDuckGo web search tool. SP4 adds 4 test files for previously untested agent nodes.

**Tech Stack:** Python 3.12, FastAPI, LangGraph, SQLAlchemy async, Redis, pytest + pytest-asyncio

---

## SP0: LLM Provider Factory

### Task 0.1: Run existing tests to get baseline

- [ ] **Step 1: Run all tests**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/ -x -q
```

Expected: 75 passed.

---

### Task 0.2: Add LLM provider config fields

**Files:**
- Modify: `app/core/config.py:13-14`

- [ ] **Step 1: Add provider config to Settings**

In `app/core/config.py`, add after line 13 (`embedding_model: str = "text-embedding-3-small"`):

```python
llm_provider: str = "openai"  # "openai" | "ollama"
ollama_model: str = "qwen2.5"
ollama_base_url: str = "http://localhost:11434"
```

- [ ] **Step 2: Verify config loads**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -c "from app.core.config import get_settings; s=get_settings(); print(s.llm_provider, s.ollama_model)"
```

Expected: `openai qwen2.5`

---

### Task 0.3: Create LLM factory

**Files:**
- Create: `app/core/llm_factory.py`
- Create: `tests/unit/core/test_llm_factory.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/core/test_llm_factory.py
import pytest
from unittest.mock import patch


class TestGetLLM:
    def test_returns_openai_by_default(self):
        import app.core.llm_factory as factory
        factory._llm_instance = None

        llm = factory.get_llm()
        from app.adapters.llm.openai import OpenAILLM
        assert isinstance(llm, OpenAILLM)

    def test_returns_ollama_when_configured(self):
        import app.core.llm_factory as factory
        factory._llm_instance = None

        with patch("app.core.llm_factory.get_settings") as mock_settings:
            mock_settings.return_value.llm_provider = "ollama"
            mock_settings.return_value.ollama_model = "llama3"
            mock_settings.return_value.ollama_base_url = "http://localhost:11434"
            llm = factory.get_llm()
            from app.adapters.llm.ollama import OllamaLLM
            assert isinstance(llm, OllamaLLM)

    def test_invalid_provider_raises(self):
        import app.core.llm_factory as factory
        factory._llm_instance = None

        with patch("app.core.llm_factory.get_settings") as mock_settings:
            mock_settings.return_value.llm_provider = "invalid"
            with pytest.raises(ValueError, match="Unknown LLM provider"):
                factory.get_llm()

    def test_singleton_returns_same_instance(self):
        import app.core.llm_factory as factory
        factory._llm_instance = None

        a = factory.get_llm()
        b = factory.get_llm()
        assert a is b
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/unit/core/test_llm_factory.py -v
```

Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Write llm_factory.py**

```python
# app/core/llm_factory.py
from app.adapters.llm.base import BaseLLM
from app.core.config import get_settings

_llm_instance: BaseLLM | None = None


def get_llm() -> BaseLLM:
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    settings = get_settings()
    provider = settings.llm_provider

    if provider == "openai":
        from app.adapters.llm.openai import OpenAILLM
        _llm_instance = OpenAILLM()
    elif provider == "ollama":
        from app.adapters.llm.ollama import OllamaLLM
        _llm_instance = OllamaLLM(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")

    return _llm_instance
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/unit/core/test_llm_factory.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/llm_factory.py tests/unit/core/test_llm_factory.py app/core/config.py
git commit -m "feat(sp0): add LLM provider factory with OpenAI/Ollama support"
```

---

### Task 0.4: Replace OpenAILLM() with get_llm() in 5 agent nodes

**Files:**
- Modify: `app/agents/understander.py`
- Modify: `app/agents/router.py`
- Modify: `app/agents/reflector.py`
- Modify: `app/agents/verifier.py`
- Modify: `app/agents/nodes.py`

- [ ] **Step 1: Replace in all 5 files**

For each file, make two edits:

`understander.py` line 3: `from app.adapters.llm.openai import OpenAILLM` → `from app.core.llm_factory import get_llm`
`understander.py` line 26: `llm = OpenAILLM()` → `llm = get_llm()`

`router.py` line 4: same import replacement
`router.py` line 65: `llm = OpenAILLM()` → `llm = get_llm()`

`reflector.py` line 3: same import replacement
`reflector.py` line 35: `llm = OpenAILLM()` → `llm = get_llm()`

`verifier.py` line 3: same import replacement
`verifier.py` line 28: `llm = OpenAILLM()` → `llm = get_llm()`

`nodes.py` line 4: same import replacement
`nodes.py` line 24: `llm = OpenAILLM()` → `llm = get_llm()`

- [ ] **Step 2: Verify all tests pass**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/ -x -q
```

Expected: 79 passed (75 original + 4 factory)

- [ ] **Step 3: Commit**

```bash
git add app/agents/understander.py app/agents/router.py app/agents/reflector.py app/agents/verifier.py app/agents/nodes.py
git commit -m "feat(sp0): replace OpenAILLM() with get_llm() in 5 agent nodes"
```

---

### Task 0.5: Replace OpenAILLM() in semantic_search tool

**Files:**
- Modify: `app/tools/semantic_search.py`

- [ ] **Step 1: Replace import + instantiation**

```
Line 4:  from app.adapters.llm.openai import OpenAILLM   →   from app.core.llm_factory import get_llm
Line 18: llm = OpenAILLM()   →   llm = get_llm()
```

- [ ] **Step 2: Verify tests pass**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/ -x -q
```

Expected: 79 passed

- [ ] **Step 3: Commit**

```bash
git add app/tools/semantic_search.py
git commit -m "feat(sp0): replace OpenAILLM() with get_llm() in semantic_search tool"
```

---

## SP1: Memory Node + QueryTrace Persistence

### Task 1.1: Implement memory_node in graph.py

**Files:**
- Modify: `app/agents/graph.py:10-12`
- Modify: `app/agents/state.py:57` (add session_id field)
- Modify: `app/services/agent_service.py` (pass session_id to state)

- [ ] **Step 1: Replace no-op memory_node**

Replace lines 10-12 of `app/agents/graph.py`:

```python
async def memory_node(state: AgentState) -> AgentState:
    """Persist conversation context to Redis short-term memory."""
    if not state.get("final_answer"):
        return state

    try:
        from app.core.di import get_redis
        from app.memory.conversation import ConversationMemory

        redis = await get_redis()
        memory = ConversationMemory(redis)

        session_id = state.get("session_id", "default")
        query = state.get("query", "")
        answer = state.get("final_answer", "")
        intent = state.get("intent", "")

        if intent:
            await memory.save_topic(session_id, intent)

        citations = state.get("citations", [])
        if citations:
            facts = [
                f"[{c.get('chunk_id', '?')}] {c.get('text', '')[:200]}"
                for c in citations[:5]
            ]
            await memory.save_facts(session_id, facts)

        window_entry = [
            {"role": "user", "content": query},
            {"role": "assistant", "content": answer[:1000]},
        ]

        existing = await memory.aload(f"session:{session_id}:window")
        existing_msgs = (existing or {}).get("messages", [])
        existing_msgs.extend(window_entry)
        await memory.save_window(session_id, existing_msgs)

        summary = answer[:500] if len(answer) > 500 else answer
        await memory.save_summary(session_id, summary)

    except Exception:
        import structlog
        logger = structlog.get_logger()
        logger.warning("memory_node_persist_failed", exc_info=True)

    return state
```

- [ ] **Step 2: Add session_id to AgentState TypedDict**

In `app/agents/state.py`, add after last field:
```python
    session_id: str
```

- [ ] **Step 3: Pass session_id in AgentService.run() initial_state**

In `app/services/agent_service.py`, add to initial_state dict:
```python
            "session_id": session_id or "",
```

- [ ] **Step 4: Verify graph compiles and tests pass**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -c "from app.agents.graph import get_graph; g=get_graph(); print('OK')"
python -m pytest tests/ -x -q
```

Expected: `OK` then 79 passed

- [ ] **Step 5: Commit**

```bash
git add app/agents/graph.py app/agents/state.py app/services/agent_service.py
git commit -m "feat(sp1): implement memory_node with Redis persistence (topic, facts, window, summary)"
```

---

### Task 1.2: Add QueryTrace persistence in AgentService

**Files:**
- Modify: `app/services/agent_service.py` (run() method)
- Modify: `app/services/rag_service.py` (query() passes db/user_id)

- [ ] **Step 1: Update AgentService.run() signature and trace INSERT**

Extend `run()` to accept `db` and `user_id`, add timing, insert QueryTrace after graph returns:

```python
import time  # add at top

class AgentService:
    def __init__(self):
        self.graph = get_graph()

    async def run(self, query: str, collection_ids: list[str],
                  db=None, user_id: str | None = None,
                  session_id: str | None = None,
                  options: dict | None = None) -> dict:
        opts = options or {}
        t0 = time.monotonic()
        # ... existing initial_state dict with added session_id ...
        initial_state: AgentState = {
            # ... all existing fields ...
            "session_id": session_id or "",
        }

        result = await self.graph.ainvoke(initial_state)
        latency_ms = int((time.monotonic() - t0) * 1000)

        trace = {
            "answer": result.get("final_answer", ""),
            "citations": result.get("citations", []),
            "agent_trace": {
                "intent": result.get("intent"),
                "sub_tasks_executed": len(result.get("sub_tasks", [])),
                "iterations": result.get("iteration", 0),
                "quality_score": result.get("quality_score", 0),
                "routes_used": _flatten_routes(result.get("routes", {})),
            },
            "uncertainty_flags": result.get("uncertainty_flags", []),
        }

        if db is not None and user_id is not None:
            try:
                from app.domain.query_trace import QueryTrace
                from app.domain.base import new_uuid
                trace_row = QueryTrace(
                    id=new_uuid(),
                    user_id=user_id,
                    session_id=session_id,
                    query=query,
                    answer=trace["answer"],
                    model_used=settings.llm_model,
                    total_tokens=0,
                    estimated_cost=0.0,
                    citations=trace["citations"],
                    agent_graph={
                        "intent": trace["agent_trace"]["intent"],
                        "iterations": trace["agent_trace"]["iterations"],
                        "quality_score": trace["agent_trace"]["quality_score"],
                        "routes_used": trace["agent_trace"]["routes_used"],
                    },
                    quality_score=trace["agent_trace"]["quality_score"],
                    iterations=trace["agent_trace"]["iterations"],
                    latency_ms=latency_ms,
                )
                db.add(trace_row)
                await db.flush()
            except Exception:
                import structlog
                logger = structlog.get_logger()
                logger.warning("trace_persist_failed", exc_info=True)

        return trace
```

- [ ] **Step 2: Update RAGService.query() call**

In `app/services/rag_service.py`, change:
```python
return await self.agent.run(query, collection_ids, session_id, options)
```
To:
```python
return await self.agent.run(query, collection_ids, db=db, user_id=user_id,
                            session_id=session_id, options=options)
```

- [ ] **Step 3: Verify tests pass**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/ -x -q
```

Expected: 79 passed

- [ ] **Step 4: Commit**

```bash
git add app/services/agent_service.py app/services/rag_service.py
git commit -m "feat(sp1): add QueryTrace INSERT persistence in AgentService.run()"
```

---

## SP2: Conversation History Injection

### Task 2.1: Load conversation context from Redis

**Files:**
- Modify: `app/services/agent_service.py`

- [ ] **Step 1: Add Redis context loading before initial_state**

In `AgentService.run()`, add after `t0 = time.monotonic()` and before `initial_state: AgentState = {`:

```python
        conversation_history = []
        if session_id:
            try:
                from app.core.di import get_redis
                from app.memory.conversation import ConversationMemory
                redis = await get_redis()
                memory = ConversationMemory(redis)
                context = await memory.get_context(session_id)
                conversation_history = context.get("window", [])
            except Exception:
                pass
```

And change `"conversation_history": [],` to:
```python
            "conversation_history": conversation_history,
```

- [ ] **Step 2: Verify tests pass**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/ -x -q
```

Expected: 79 passed

- [ ] **Step 3: Commit**

```bash
git add app/services/agent_service.py
git commit -m "feat(sp2): inject conversation history from Redis into AgentState"
```

---

## SP3: Trace API + Web Search Tool

### Task 3.1: Implement GET /query/{trace_id}/trace

**Files:**
- Modify: `app/api/v1/queries.py:64-66`

- [ ] **Step 1: Replace stub endpoint**

Replace lines 64-66 in `app/api/v1/queries.py`:

```python
@router.get("/{trace_id}/trace")
async def get_trace(trace_id: str, db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)):
    from sqlalchemy import select
    from app.domain.query_trace import QueryTrace
    result = await db.execute(
        select(QueryTrace).where(
            QueryTrace.id == trace_id,
            QueryTrace.user_id == user.id,
        )
    )
    trace = result.scalar_one_or_none()
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return {
        "trace_id": trace.id,
        "session_id": trace.session_id,
        "query": trace.query,
        "answer": trace.answer,
        "model_used": trace.model_used,
        "total_tokens": trace.total_tokens,
        "estimated_cost": trace.estimated_cost,
        "citations": trace.citations,
        "agent_graph": trace.agent_graph,
        "quality_score": trace.quality_score,
        "iterations": trace.iterations,
        "latency_ms": trace.latency_ms,
        "created_at": trace.created_at.isoformat() if trace.created_at else None,
    }
```

Ensure `HTTPException` is in the imports at top:
```python
from fastapi import APIRouter, Depends, HTTPException
```

- [ ] **Step 2: Verify tests pass**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/ -x -q
```

Expected: 79 passed

- [ ] **Step 3: Commit**

```bash
git add app/api/v1/queries.py
git commit -m "feat(sp3): implement GET /query/{trace_id}/trace from QueryTrace table"
```

---

### Task 3.2: Create Web Search tool

**Files:**
- Create: `app/tools/web_search.py`
- Modify: `app/tools/__init__.py` (register)
- Modify: `app/agents/router.py` (fallback rule)
- Modify: `app/agents/state.py` (add enable_web_search)
- Modify: `app/services/agent_service.py` (pass enable_web_search)

- [ ] **Step 1: Write web_search.py**

```python
# app/tools/web_search.py
import httpx
from app.tools.base import BaseTool

WEB_SEARCH_PROMPT = """Generate a concise search query from this task description.
Output ONLY the search query string, nothing else."""


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Web search via DuckDuckGo — for recent information not in local docs"

    async def _generate_query(self, task_description: str) -> str:
        try:
            from app.core.llm_factory import get_llm
            llm = get_llm()
            result = await llm.agenerate(
                f"{WEB_SEARCH_PROMPT}\nTask: {task_description}"
            )
            return result.strip()[:200]
        except Exception:
            return task_description

    async def arun(
        self, query: str, collection_ids: list[str] | None = None,
        top_k: int = 5
    ) -> list[dict]:
        search_query = await self._generate_query(query)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": search_query, "format": "json", "no_html": "1"},
                )
                data = resp.json()
                results = []
                if data.get("AbstractText"):
                    results.append({
                        "chunk_id": f"web_{hash(data['AbstractURL']) & 0x7FFFFFFF:08x}",
                        "document_id": "web_search",
                        "text": data["AbstractText"],
                        "score": 0.6,
                        "source": "web",
                        "metadata": {"url": data.get("AbstractURL", "")},
                    })
                for topic in data.get("RelatedTopics", [])[:top_k]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        results.append({
                            "chunk_id": f"web_{hash(topic.get('FirstURL', '')) & 0x7FFFFFFF:08x}",
                            "document_id": "web_search",
                            "text": topic["Text"],
                            "score": 0.4,
                            "source": "web",
                            "metadata": {"url": topic.get("FirstURL", "")},
                        })
                return results
        except Exception:
            return []
```

- [ ] **Step 2: Register in ToolRegistry**

In `app/tools/__init__.py`, in `get_tool_registry()`, add after the `_registry.register(KeywordSearchTool())` line:

```python
        from app.tools.web_search import WebSearchTool
        _registry.register(WebSearchTool())
```

- [ ] **Step 3: Add web search fallback rule in router**

In `app/agents/router.py`, add to `FALLBACK_RULES` dict:
```python
    "web": ["web_search"],
```

- [ ] **Step 4: Add enable_web_search to AgentState**

In `app/agents/state.py`, add after last field:
```python
    enable_web_search: bool
```

- [ ] **Step 5: Pass enable_web_search through AgentService**

In `app/services/agent_service.py` initial_state dict, add:
```python
            "enable_web_search": opts.get("enable_web_search", False),
```

- [ ] **Step 6: Verify tests pass**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/ -x -q
```

Expected: 79 passed

- [ ] **Step 7: Commit**

```bash
git add app/tools/web_search.py app/tools/__init__.py app/agents/router.py app/agents/state.py app/services/agent_service.py
git commit -m "feat(sp3): add web search tool with DuckDuckGo integration + routing"
```

---

## SP4: Test Coverage

### Task 4.1: Understander node tests

**Files:**
- Create: `tests/unit/agents/test_understander.py`

- [ ] **Step 1: Write tests**

```python
# tests/unit/agents/test_understander.py
import pytest
from unittest.mock import patch, AsyncMock


def _make_state(query="What is RAG?", history=None):
    return {
        "query": query,
        "conversation_history": history or [],
        "intent": "",
        "rewritten_query": "",
        "sub_tasks": [],
        "routes": {},
        "retrieved": [],
        "raw_milvus_hits": [],
        "raw_kg_results": [],
        "raw_keyword_hits": [],
        "reflection_notes": "",
        "missing_info": [],
        "quality_score": 0.0,
        "need_another_round": False,
        "draft_answer": "",
        "verified_claims": [],
        "supplement_queries": [],
        "need_supplement": False,
        "final_answer": "",
        "citations": [],
        "uncertainty_flags": [],
        "warnings": [],
        "bare_minimum_mode": False,
        "iteration": 0,
        "max_iterations": 5,
        "prev_score": None,
        "collection_ids": [],
    }


class TestUnderstandNode:
    async def test_populates_intent_and_subtasks(self):
        mock_llm = AsyncMock()
        mock_llm.agenerate_structured.return_value = {
            "intent": "fact",
            "rewritten_query": "What is retrieval augmented generation?",
            "sub_tasks": [
                {"id": "t1", "description": "Define RAG", "intent": "fact", "depends_on": []},
            ],
        }

        with patch("app.agents.understander.get_llm", return_value=mock_llm):
            from app.agents.understander import understand_node
            state = await understand_node(_make_state("What is RAG?"))

        assert state["intent"] == "fact"
        assert "retrieval augmented" in state["rewritten_query"].lower()
        assert len(state["sub_tasks"]) == 1
        assert state["sub_tasks"][0]["status"] == "pending"
        assert state["sub_tasks"][0]["id"] == "t1"

    async def test_handles_empty_subtasks(self):
        mock_llm = AsyncMock()
        mock_llm.agenerate_structured.return_value = {
            "intent": "fact",
            "rewritten_query": "",
            "sub_tasks": [],
        }

        with patch("app.agents.understander.get_llm", return_value=mock_llm):
            from app.agents.understander import understand_node
            state = await understand_node(_make_state(""))

        assert state["intent"] == "fact"
        assert state["sub_tasks"] == []
```

- [ ] **Step 2: Run tests**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/unit/agents/test_understander.py -v
```

Expected: 2 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/agents/test_understander.py
git commit -m "test(sp4): add understander node tests (2 tests)"
```

---

### Task 4.2: Reflector node tests

**Files:**
- Create: `tests/unit/agents/test_reflector.py`

- [ ] **Step 1: Write tests**

```python
# tests/unit/agents/test_reflector.py
import pytest
from unittest.mock import patch, AsyncMock


def _make_state(query="test", retrieved=None):
    return {
        "query": query,
        "conversation_history": [],
        "intent": "fact",
        "rewritten_query": query,
        "sub_tasks": [],
        "routes": {},
        "retrieved": retrieved or [
            {"chunk_id": "c1", "document_id": "d1", "text": "RAG combines retrieval with generation.", "score": 0.9, "source": "milvus", "metadata": {}},
        ],
        "raw_milvus_hits": [],
        "raw_kg_results": [],
        "raw_keyword_hits": [],
        "reflection_notes": "",
        "missing_info": [],
        "quality_score": 0.0,
        "need_another_round": False,
        "draft_answer": "",
        "verified_claims": [],
        "supplement_queries": [],
        "need_supplement": False,
        "final_answer": "",
        "citations": [],
        "uncertainty_flags": [],
        "warnings": [],
        "bare_minimum_mode": False,
        "iteration": 0,
        "max_iterations": 5,
        "prev_score": None,
        "collection_ids": [],
    }


class TestReflectorNode:
    async def test_generates_draft_and_reflection(self):
        mock_llm = AsyncMock()
        mock_llm.agenerate.return_value = "RAG combines retrieval with generation."
        mock_llm.agenerate_structured.return_value = {
            "reflection_notes": "Good coverage",
            "missing_info": [],
            "quality_score": 0.85,
        }

        with patch("app.agents.reflector.get_llm", return_value=mock_llm):
            from app.agents.reflector import reflector_node
            state = await reflector_node(_make_state())

        assert len(state["draft_answer"]) > 0
        assert state["quality_score"] == 0.85
        assert state["reflection_notes"] == "Good coverage"

    async def test_low_quality_triggers_another_round(self):
        mock_llm = AsyncMock()
        mock_llm.agenerate.return_value = "Short."
        mock_llm.agenerate_structured.return_value = {
            "reflection_notes": "Incomplete",
            "missing_info": ["Missing detail X"],
            "quality_score": 0.3,
        }

        with patch("app.agents.reflector.get_llm", return_value=mock_llm):
            from app.agents.reflector import reflector_node
            state = await reflector_node(_make_state())

        assert state["quality_score"] == 0.3
        assert state["need_another_round"] is True
        assert "Missing detail X" in state["missing_info"]
```

- [ ] **Step 2: Run tests**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/unit/agents/test_reflector.py -v
```

Expected: 2 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/agents/test_reflector.py
git commit -m "test(sp4): add reflector node tests (2 tests)"
```

---

### Task 4.3: Verifier node tests

**Files:**
- Create: `tests/unit/agents/test_verifier.py`

- [ ] **Step 1: Write tests**

```python
# tests/unit/agents/test_verifier.py
import pytest
from unittest.mock import patch, AsyncMock


def _make_state(draft="", retrieved=None):
    return {
        "query": "test",
        "conversation_history": [],
        "intent": "fact",
        "rewritten_query": "test",
        "sub_tasks": [],
        "routes": {},
        "retrieved": retrieved or [
            {"chunk_id": "c1", "document_id": "d1", "text": "Supporting evidence.", "score": 0.9, "source": "milvus", "metadata": {}},
        ],
        "raw_milvus_hits": [],
        "raw_kg_results": [],
        "raw_keyword_hits": [],
        "reflection_notes": "",
        "missing_info": [],
        "quality_score": 0.0,
        "need_another_round": False,
        "draft_answer": draft,
        "verified_claims": [],
        "supplement_queries": [],
        "need_supplement": False,
        "final_answer": "",
        "citations": [],
        "uncertainty_flags": [],
        "warnings": [],
        "bare_minimum_mode": False,
        "iteration": 0,
        "max_iterations": 5,
        "prev_score": None,
        "collection_ids": [],
    }


class TestVerifierNode:
    async def test_verifies_claims_and_detects_unverified(self):
        mock_llm = AsyncMock()
        mock_llm.agenerate_structured.return_value = {
            "claims": [
                {"text": "Claim A", "status": "verified", "source_chunk_id": "c1", "contradiction_note": None},
                {"text": "Claim B", "status": "unverified", "source_chunk_id": None, "contradiction_note": None, "search_query": "find B"},
            ]
        }

        with patch("app.agents.verifier.get_llm", return_value=mock_llm):
            from app.agents.verifier import verifier_node
            state = await verifier_node(_make_state(draft="Claim A. Claim B."))

        assert len(state["verified_claims"]) == 2
        assert state["verified_claims"][0]["status"] == "verified"
        assert state["verified_claims"][1]["status"] == "unverified"

    async def test_all_unverified_triggers_supplement(self):
        mock_llm = AsyncMock()
        mock_llm.agenerate_structured.return_value = {
            "claims": [
                {"text": "X", "status": "unverified", "source_chunk_id": None, "contradiction_note": None, "search_query": "find X"},
                {"text": "Y", "status": "unverified", "source_chunk_id": None, "contradiction_note": None, "search_query": "find Y"},
                {"text": "Z", "status": "unverified", "source_chunk_id": None, "contradiction_note": None},
            ]
        }

        with patch("app.agents.verifier.get_llm", return_value=mock_llm):
            from app.agents.verifier import verifier_node
            state = await verifier_node(_make_state(draft="X. Y. Z."))

        assert state["need_supplement"] is True
        assert len(state["supplement_queries"]) == 2

    async def test_empty_draft_returns_early_no_llm(self):
        from app.agents.verifier import verifier_node
        state = await verifier_node(_make_state(draft=""))
        assert state["verified_claims"] == []
        assert state["need_supplement"] is False
```

- [ ] **Step 2: Run tests**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/unit/agents/test_verifier.py -v
```

Expected: 3 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/agents/test_verifier.py
git commit -m "test(sp4): add verifier node tests (3 tests)"
```

---

### Task 4.4: Synthesize node + Web search tool tests

**Files:**
- Create: `tests/unit/agents/test_synthesizer.py`
- Create: `tests/unit/tools/test_web_search.py`

- [ ] **Step 1: Write synthesizer tests**

```python
# tests/unit/agents/test_synthesizer.py
import pytest
from unittest.mock import patch, AsyncMock


def _make_state(query="test", retrieved=None):
    return {
        "query": query,
        "conversation_history": [],
        "intent": "fact",
        "rewritten_query": query,
        "sub_tasks": [],
        "routes": {},
        "retrieved": retrieved or [
            {"chunk_id": "c1", "document_id": "d1", "text": "RAG combines retrieval with generation.", "score": 0.9, "source": "milvus", "metadata": {}},
        ],
        "raw_milvus_hits": [],
        "raw_kg_results": [],
        "raw_keyword_hits": [],
        "reflection_notes": "",
        "missing_info": [],
        "quality_score": 0.0,
        "need_another_round": False,
        "draft_answer": "",
        "verified_claims": [
            {"text": "Good", "status": "verified", "source_chunk_id": "c1", "contradiction_note": None},
        ],
        "supplement_queries": [],
        "need_supplement": False,
        "final_answer": "",
        "citations": [],
        "uncertainty_flags": [],
        "warnings": [],
        "bare_minimum_mode": False,
        "iteration": 2,
        "max_iterations": 5,
        "prev_score": None,
        "collection_ids": [],
    }


class TestSynthesizeNode:
    async def test_synthesizes_answer_with_citations(self):
        mock_llm = AsyncMock()
        mock_llm.agenerate.return_value = "RAG combines retrieval with generation [c:c1]."

        with patch("app.agents.nodes.get_llm", return_value=mock_llm):
            from app.agents.nodes import synthesize_node
            state = await synthesize_node(_make_state())

        assert len(state["final_answer"]) > 0
        assert len(state["citations"]) == 1
        assert state["citations"][0]["chunk_id"] == "c1"

    async def test_empty_retrieved_returns_graceful_message(self):
        from app.agents.nodes import synthesize_node
        state = await synthesize_node(_make_state(retrieved=[]))

        assert "cannot answer" in state["final_answer"].lower()
        assert state["citations"] == []
        assert len(state["uncertainty_flags"]) > 0
```

- [ ] **Step 2: Write web search tool test**

```python
# tests/unit/tools/test_web_search.py
import pytest
from unittest.mock import patch, AsyncMock


class TestWebSearchTool:
    async def test_registered_in_registry(self):
        from app.tools import get_tool_registry
        registry = get_tool_registry()
        assert "web_search" in registry.tool_names

    async def test_arun_returns_empty_on_http_error(self):
        with patch("httpx.AsyncClient.get", side_effect=Exception("Network error")):
            from app.tools.web_search import WebSearchTool
            tool = WebSearchTool()
            results = await tool.arun("test query")
            assert results == []

    async def test_arun_parses_duckduckgo_response(self):
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "AbstractText": "RAG stands for Retrieval-Augmented Generation.",
            "AbstractURL": "https://example.com/rag",
            "RelatedTopics": [{"Text": "RAG in NLP", "FirstURL": "https://example.com/1"}],
        }

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            from app.tools.web_search import WebSearchTool
            tool = WebSearchTool()
            with patch.object(tool, "_generate_query", return_value="test query"):
                results = await tool.arun("test query")

            assert len(results) >= 1
            assert results[0]["source"] == "web"
            assert "RAG" in results[0]["text"]
```

- [ ] **Step 3: Run tests**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/unit/agents/test_synthesizer.py tests/unit/tools/test_web_search.py -v
```

Expected: 5 PASS

- [ ] **Step 4: Commit**

```bash
git add tests/unit/agents/test_synthesizer.py tests/unit/tools/test_web_search.py
git commit -m "test(sp4): add synthesizer node + web search tool tests (5 tests)"
```

---

### Task 4.5: Final integration test run

- [ ] **Step 1: Run full test suite**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/ -x -q -v
```

Expected: ~91 tests passed (75 original + 4 factory + 2 understander + 2 reflector + 3 verifier + 2 synthesizer + 3 web search)

- [ ] **Step 2: Check frontend TypeScript**

```bash
cd D:\artificialintelligent\AgentRAGProject\frontend && npx tsc --noEmit
```

Expected: zero errors

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat(phase4): complete SP0-SP4 — LLM factory, memory node, query trace, conversation history, trace API, web search, 16 new tests"
```

---

## Summary

| SP | Tasks | New Files | Modified Files | Tests Added |
|----|-------|-----------|---------------|-------------|
| SP0 | 0.1-0.5 | `llm_factory.py`, `test_llm_factory.py` | `config.py`, 5 agent nodes, `semantic_search.py` | 4 |
| SP1 | 1.1-1.2 | — | `graph.py`, `agent_service.py`, `rag_service.py`, `state.py` | 0 |
| SP2 | 2.1 | — | `agent_service.py` | 0 |
| SP3 | 3.1-3.2 | `web_search.py` | `queries.py`, `router.py`, `tools/__init__.py`, `state.py`, `agent_service.py` | 0 |
| SP4 | 4.1-4.5 | 4 test files | — | 12 |
| **Total** | **13 tasks** | **6 new files** | **~15 modified** | **16 new tests** |