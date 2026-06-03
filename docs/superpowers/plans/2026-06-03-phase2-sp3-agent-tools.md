# Phase 2 SP3: Agent + Tools 升级 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Agent 从单后端（仅 Milvus）升级为多后端自适应检索系统：LLM 动态路由 + 多路径 Executor + 3 个 Tool

**Architecture:** 新增 `app/tools/` 模块（BaseTool ABC + 3 Tool 实现 + ToolRegistry 单例），重写 Router（LLM 动态路由 + fallback）和 Executor（依赖解析 + 并行调度 + 归一化），下游节点和 Graph 结构零改动

**Tech Stack:** Python 3.12+, LangGraph, OpenAILLM (已有), MilvusStore (已有), Neo4jKGStore (已有), ElasticsearchStore (已有)

**Spec:** `docs/superpowers/specs/2026-06-03-phase2-sp3-agent-tools-design.md`

---

### Task 1: BaseTool ABC + ToolRegistry

**Files:**
- Create: `app/tools/base.py`
- Create: `app/tools/__init__.py`
- Test: `tests/unit/tools/test_registry.py`

- [ ] **Step 1: Write failing tests for ToolRegistry**

```python
# tests/unit/tools/test_registry.py
import pytest
from app.tools.base import BaseTool
from app.tools import ToolRegistry


class _FakeTool(BaseTool):
    name = "fake"
    description = "A fake tool for testing"

    async def arun(self, query: str, collection_ids: list[str], top_k: int = 10) -> list[dict]:
        return [{"chunk_id": "1", "text": query, "score": 1.0, "source": "test"}]


@pytest.mark.asyncio
async def test_registry_register_and_get():
    registry = ToolRegistry()
    tool = _FakeTool()
    registry.register(tool)
    assert registry.get("fake") is tool


@pytest.mark.asyncio
async def test_registry_get_unknown_raises():
    registry = ToolRegistry()
    with pytest.raises(KeyError, match="Unknown tool: missing"):
        registry.get("missing")


@pytest.mark.asyncio
async def test_registry_tool_names_and_descriptions():
    registry = ToolRegistry()
    tool = _FakeTool()
    registry.register(tool)
    assert registry.tool_names == ["fake"]
    assert "fake: A fake tool for testing" in registry.tool_descriptions
```

Run: `pytest tests/unit/tools/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.tools'`

- [ ] **Step 2: Create BaseTool ABC and ToolRegistry**

```python
# app/tools/base.py
from abc import ABC, abstractmethod


class BaseTool(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    async def arun(
        self, query: str, collection_ids: list[str], top_k: int = 10
    ) -> list[dict]:
        """Execute retrieval, return list of result dicts.

        Each dict MUST include:
          - chunk_id: str
          - text: str
          - score: float
          - source: str  ("milvus" | "kg" | "keyword")

        Optional:
          - document_id: str
        """
        ...
```

```python
# app/tools/__init__.py
from app.tools.base import BaseTool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    @property
    def tool_descriptions(self) -> str:
        return "\n".join(
            f"- {t.name}: {t.description}" for t in self._tools.values()
        )


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        from app.tools.semantic_search import SemanticSearchTool  # noqa: F811
        from app.tools.kg_search import KGSearchTool
        from app.tools.keyword_search import KeywordSearchTool
        _registry = ToolRegistry()
        _registry.register(SemanticSearchTool())
        _registry.register(KGSearchTool())
        _registry.register(KeywordSearchTool())
    return _registry


__all__ = ["BaseTool", "ToolRegistry", "get_tool_registry"]
```

Run: `pytest tests/unit/tools/test_registry.py -v`
Expected: 3 PASS

- [ ] **Step 3: Commit**

```bash
git add app/tools/__init__.py app/tools/base.py tests/unit/tools/test_registry.py
git commit -m "feat(sp3): add BaseTool ABC and ToolRegistry"
```

---

### Task 2: SemanticSearchTool

**Files:**
- Create: `app/tools/semantic_search.py`
- Test: `tests/unit/tools/test_semantic_search.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/tools/test_semantic_search.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.tools.semantic_search import SemanticSearchTool


@pytest.mark.asyncio
async def test_semantic_search_returns_unified_format():
    tool = SemanticSearchTool()
    assert tool.name == "semantic_search"
    assert "Milvus" in tool.description

    with patch("app.tools.semantic_search.OpenAIEmbedding") as mock_emb, \
         patch("app.tools.semantic_search.MilvusStore") as mock_store, \
         patch("app.tools.semantic_search.OpenAILLM") as mock_llm:

        mock_llm_instance = MagicMock()
        mock_llm_instance.agenerate_structured = AsyncMock(
            return_value=["variant 1", "variant 2", "variant 3"]
        )
        mock_llm.return_value = mock_llm_instance

        mock_emb_instance = MagicMock()
        mock_emb_instance.aembed_query = AsyncMock(return_value=[0.1] * 1536)
        mock_emb.return_value = mock_emb_instance

        from app.adapters.vector_store.base import SearchResult
        mock_store_instance = MagicMock()
        mock_store_instance.search = AsyncMock(return_value=[
            SearchResult(chunk_id="c1", document_id="d1", text="hello world", score=0.95, metadata={})
        ])
        mock_store.return_value = mock_store_instance

        results = await tool.arun("test query", ["col1"])

        assert len(results) > 0
        assert results[0]["chunk_id"] == "c1"
        assert results[0]["document_id"] == "d1"
        assert results[0]["text"] == "hello world"
        assert results[0]["score"] == 0.95
        assert results[0]["source"] == "milvus"


@pytest.mark.asyncio
async def test_semantic_search_deduplicates_by_chunk_id():
    tool = SemanticSearchTool()
    with patch("app.tools.semantic_search.OpenAIEmbedding") as mock_emb, \
         patch("app.tools.semantic_search.MilvusStore") as mock_store, \
         patch("app.tools.semantic_search.OpenAILLM") as mock_llm:

        mock_llm_instance = MagicMock()
        mock_llm_instance.agenerate_structured = AsyncMock(return_value=["v1"])
        mock_llm.return_value = mock_llm_instance

        mock_emb_instance = MagicMock()
        mock_emb_instance.aembed_query = AsyncMock(return_value=[0.1] * 1536)
        mock_emb.return_value = mock_emb_instance

        from app.adapters.vector_store.base import SearchResult
        mock_store_instance = MagicMock()
        mock_store_instance.search = AsyncMock(return_value=[
            SearchResult(chunk_id="c1", document_id="d1", text="text", score=0.9, metadata={}),
            SearchResult(chunk_id="c1", document_id="d1", text="text", score=0.8, metadata={}),
        ])
        mock_store.return_value = mock_store_instance

        results = await tool.arun("test", ["col1"])
        assert len(results) == 1  # deduplicated


@pytest.mark.asyncio
async def test_semantic_search_empty_collections():
    tool = SemanticSearchTool()
    results = await tool.arun("test", [])
    assert results == []


@pytest.mark.asyncio
async def test_semantic_search_expand_queries_failure_uses_original():
    tool = SemanticSearchTool()
    with patch("app.tools.semantic_search.OpenAIEmbedding") as mock_emb, \
         patch("app.tools.semantic_search.MilvusStore") as mock_store, \
         patch("app.tools.semantic_search.OpenAILLM") as mock_llm:

        mock_llm_instance = MagicMock()
        mock_llm_instance.agenerate_structured = AsyncMock(side_effect=Exception("LLM down"))
        mock_llm.return_value = mock_llm_instance

        mock_emb_instance = MagicMock()
        mock_emb_instance.aembed_query = AsyncMock(return_value=[0.1] * 1536)
        mock_emb.return_value = mock_emb_instance

        from app.adapters.vector_store.base import SearchResult
        mock_store_instance = MagicMock()
        mock_store_instance.search = AsyncMock(return_value=[
            SearchResult(chunk_id="c1", document_id="d1", text="text", score=0.9, metadata={})
        ])
        mock_store.return_value = mock_store_instance

        results = await tool.arun("original query", ["col1"])
        assert len(results) == 1  # falls back to original query
```

Run: `pytest tests/unit/tools/test_semantic_search.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.tools.semantic_search'`

- [ ] **Step 2: Implement SemanticSearchTool**

```python
# app/tools/semantic_search.py
from app.tools.base import BaseTool
from app.adapters.embedding.openai_embed import OpenAIEmbedding
from app.adapters.vector_store.milvus import MilvusStore
from app.adapters.llm.openai import OpenAILLM

QUERY_EXPAND_PROMPT = """Generate {n} alternative search queries for the given task description.
The variants should use different wording, synonyms, and perspectives to maximize recall.
Output JSON array of strings only.
"""


class SemanticSearchTool(BaseTool):
    name = "semantic_search"
    description = "Vector semantic search via Milvus — best for fact lookup and concept matching"

    async def _expand_queries(self, query: str, n: int = 3) -> list[str]:
        try:
            llm = OpenAILLM()
            result = await llm.agenerate_structured(
                QUERY_EXPAND_PROMPT.format(n=n) + f"\nTask: {query}",
                output_schema={"type": "array", "items": {"type": "string"}},
            )
            return result if isinstance(result, list) else [query]
        except Exception:
            return [query]

    async def arun(
        self, query: str, collection_ids: list[str], top_k: int = 10
    ) -> list[dict]:
        embedder = OpenAIEmbedding()
        store = MilvusStore()
        variants = await self._expand_queries(query)
        all_hits: list[dict] = []
        seen: set[str] = set()

        for variant in variants:
            qe = await embedder.aembed_query(variant)
            for col_id in collection_ids:
                col_name = f"col_{col_id}"
                try:
                    hits = await store.search(col_name, qe, top_k=top_k)
                    for hit in hits:
                        if hit.chunk_id not in seen:
                            all_hits.append({
                                "chunk_id": hit.chunk_id,
                                "document_id": hit.document_id,
                                "text": hit.text,
                                "score": hit.score,
                                "source": "milvus",
                            })
                            seen.add(hit.chunk_id)
                except Exception:
                    continue

        return all_hits
```

Run: `pytest tests/unit/tools/test_semantic_search.py -v`
Expected: 4 PASS

- [ ] **Step 3: Commit**

```bash
git add app/tools/semantic_search.py tests/unit/tools/test_semantic_search.py
git commit -m "feat(sp3): add SemanticSearchTool with query expansion"
```

---

### Task 3: KGSearchTool

**Files:**
- Create: `app/tools/kg_search.py`
- Test: `tests/unit/tools/test_kg_search.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/tools/test_kg_search.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.tools.kg_search import KGSearchTool


@pytest.mark.asyncio
async def test_kg_search_entities_and_relations():
    tool = KGSearchTool()
    assert tool.name == "kg_search"
    assert "Neo4j" in tool.description

    with patch("app.tools.kg_search.Neo4jKGStore") as mock_kg:
        mock_instance = MagicMock()
        mock_instance.asearch_entities = AsyncMock(return_value=[
            {"id": "ent1", "name": "Zhang San", "type": "PERSON"},
            {"id": "ent2", "name": "Tencent", "type": "ORG"},
        ])
        mock_instance.aquery_relations = AsyncMock(return_value=[
            {"from": "ent1", "type": "WORKS_AT", "to": "ent2"},
        ])
        mock_kg.return_value = mock_instance

        results = await tool.arun("Zhang San", [])

        assert len(results) >= 3  # 2 entities + 1 relation
        entity_result = [r for r in results if "Entity:" in r["text"]]
        assert len(entity_result) == 2
        assert entity_result[0]["source"] == "kg"
        assert entity_result[0]["score"] == 0.5
        rel_result = [r for r in results if "→" in r["text"]]
        assert len(rel_result) == 1
        assert "WORKS_AT" in rel_result[0]["text"]


@pytest.mark.asyncio
async def test_kg_search_empty_results():
    tool = KGSearchTool()
    with patch("app.tools.kg_search.Neo4jKGStore") as mock_kg:
        mock_instance = MagicMock()
        mock_instance.asearch_entities = AsyncMock(return_value=[])
        mock_kg.return_value = mock_instance

        results = await tool.arun("nonexistent", [])
        assert results == []


@pytest.mark.asyncio
async def test_kg_search_limits_relation_expansion():
    """Only top 5 entities get relations expanded."""
    tool = KGSearchTool()
    with patch("app.tools.kg_search.Neo4jKGStore") as mock_kg:
        mock_instance = MagicMock()
        mock_instance.asearch_entities = AsyncMock(return_value=[
            {"id": f"ent{i}", "name": f"Entity{i}", "type": "THING"}
            for i in range(10)
        ])
        mock_instance.aquery_relations = AsyncMock(return_value=[])
        mock_kg.return_value = mock_instance

        results = await tool.arun("test", [])
        assert len(results) == 10
        assert mock_instance.aquery_relations.call_count == 5
```

Run: `pytest tests/unit/tools/test_kg_search.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 2: Implement KGSearchTool**

```python
# app/tools/kg_search.py
from urllib.parse import quote
from app.tools.base import BaseTool
from app.adapters.kg.neo4j import Neo4jKGStore


class KGSearchTool(BaseTool):
    name = "kg_search"
    description = "Knowledge graph search via Neo4j — best for entity relationships and multi-hop queries"

    async def arun(
        self, query: str, collection_ids: list[str], top_k: int = 10
    ) -> list[dict]:
        kg = Neo4jKGStore()
        entities = await kg.asearch_entities(query, top_k=top_k)
        if not entities:
            return []

        results: list[dict] = []
        for ent in entities:
            safe_id = quote(ent["id"], safe="")
            results.append({
                "chunk_id": f"kg-entity-{safe_id}",
                "text": f"Entity: {ent['name']} ({ent['type']})",
                "score": 0.5,
                "source": "kg",
            })

        for ent in entities[:5]:
            try:
                relations = await kg.aquery_relations(ent["id"])
                for rel in relations:
                    results.append({
                        "chunk_id": f"kg-rel-{quote(rel['from'], safe='')}-{quote(rel['to'], safe='')}",
                        "text": f"{rel['from']} → {rel['type']} → {rel['to']}",
                        "score": 0.5,
                        "source": "kg",
                    })
            except Exception:
                continue

        return results
```

Run: `pytest tests/unit/tools/test_kg_search.py -v`
Expected: 3 PASS

- [ ] **Step 3: Commit**

```bash
git add app/tools/kg_search.py tests/unit/tools/test_kg_search.py
git commit -m "feat(sp3): add KGSearchTool with entity + relation expansion"
```

---

### Task 4: KeywordSearchTool

**Files:**
- Create: `app/tools/keyword_search.py`
- Test: `tests/unit/tools/test_keyword_search.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/tools/test_keyword_search.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.tools.keyword_search import KeywordSearchTool


@pytest.mark.asyncio
async def test_keyword_search_returns_unified_format():
    tool = KeywordSearchTool()
    assert tool.name == "keyword_search"
    assert "Elasticsearch" in tool.description

    with patch("app.tools.keyword_search.ElasticsearchStore") as mock_es:
        mock_instance = MagicMock()
        mock_instance.asearch = AsyncMock(return_value=[
            {"document_id": "doc1", "title": "Title", "text": "Full text content here", "score": 2.5},
        ])
        mock_es.return_value = mock_instance

        results = await tool.arun("test", ["col1"])

        assert len(results) == 1
        assert results[0]["chunk_id"] == "doc1"
        assert results[0]["document_id"] == "doc1"
        assert results[0]["text"] == "Full text content here"
        assert results[0]["score"] == 2.5
        assert results[0]["source"] == "keyword"


@pytest.mark.asyncio
async def test_keyword_search_truncates_long_text():
    tool = KeywordSearchTool()
    long_text = "x" * 1000
    with patch("app.tools.keyword_search.ElasticsearchStore") as mock_es:
        mock_instance = MagicMock()
        mock_instance.asearch = AsyncMock(return_value=[
            {"document_id": "doc1", "title": "T", "text": long_text, "score": 1.0},
        ])
        mock_es.return_value = mock_instance

        results = await tool.arun("test", ["col1"])
        assert len(results[0]["text"]) <= 503  # 500 + "..." at most
        assert results[0]["text"].endswith("...")


@pytest.mark.asyncio
async def test_keyword_search_empty_collections():
    tool = KeywordSearchTool()
    results = await tool.arun("test", [])
    assert results == []
```

Run: `pytest tests/unit/tools/test_keyword_search.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 2: Implement KeywordSearchTool**

```python
# app/tools/keyword_search.py
from app.tools.base import BaseTool
from app.adapters.search.elasticsearch import ElasticsearchStore

TRUNCATE_LIMIT = 500


class KeywordSearchTool(BaseTool):
    name = "keyword_search"
    description = "Full-text keyword search via Elasticsearch with IK tokenizer — best for exact match and term queries"

    async def arun(
        self, query: str, collection_ids: list[str], top_k: int = 10
    ) -> list[dict]:
        es = ElasticsearchStore()
        results: list[dict] = []

        for col_id in collection_ids:
            try:
                hits = await es.asearch(col_id, query, top_k=top_k)
                for h in hits:
                    text = h["text"]
                    if len(text) > TRUNCATE_LIMIT:
                        text = text[:TRUNCATE_LIMIT] + "..."
                    results.append({
                        "chunk_id": h["document_id"],
                        "document_id": h["document_id"],
                        "text": text,
                        "score": h["score"],
                        "source": "keyword",
                    })
            except Exception:
                continue

        return results
```

Run: `pytest tests/unit/tools/test_keyword_search.py -v`
Expected: 3 PASS

- [ ] **Step 3: Commit**

```bash
git add app/tools/keyword_search.py tests/unit/tools/test_keyword_search.py
git commit -m "feat(sp3): add KeywordSearchTool with text truncation"
```

---

### Task 5: AgentState routes type change

**Files:**
- Modify: `app/agents/state.py:36`

- [ ] **Step 1: Change routes type**

In `app/agents/state.py`, change line 36:
```python
# Before:
routes: Dict[str, str]
# After:
routes: Dict[str, list[str]]
```

- [ ] **Step 2: Verify syntax and existing tests**

Run: `python -c "from app.agents.state import AgentState; print('OK')"`
Expected: OK

Run: `pytest tests/unit/agents/test_graph.py -v`
Expected: 3 PASS

- [ ] **Step 3: Commit**

```bash
git add app/agents/state.py
git commit -m "feat(sp3): change routes type from Dict[str, str] to Dict[str, list[str]]"
```

---

### Task 6: Router rewrite

**Files:**
- Modify: `app/agents/router.py` (full rewrite)
- Modify: `tests/unit/agents/test_router.py` (full rewrite)

- [ ] **Step 1: Write failing tests for new Router**

```python
# tests/unit/agents/test_router.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.state import AgentState
from app.agents.router import route_node, FALLBACK_RULES


def _make_state(sub_tasks=None):
    state: AgentState = {
        "query": "test", "conversation_history": [],
        "intent": "", "rewritten_query": "",
        "sub_tasks": sub_tasks or [],
        "routes": {}, "retrieved": [], "raw_milvus_hits": [], "raw_kg_results": [], "raw_keyword_hits": [],
        "reflection_notes": "", "missing_info": [], "quality_score": 0.0, "need_another_round": False,
        "draft_answer": "", "verified_claims": [], "supplement_queries": [], "need_supplement": False,
        "final_answer": "", "citations": [], "uncertainty_flags": [], "warnings": [], "bare_minimum_mode": False,
        "iteration": 0, "max_iterations": 5, "prev_score": None, "collection_ids": [],
    }
    return state


@pytest.mark.asyncio
async def test_router_llm_routing():
    with patch("app.agents.router.OpenAILLM") as mock_llm, \
         patch("app.agents.router.get_tool_registry") as mock_registry:

        mock_registry_instance = MagicMock()
        mock_registry_instance.tool_names = ["semantic_search", "kg_search", "keyword_search"]
        mock_registry_instance.tool_descriptions = "- semantic_search: desc\n- kg_search: desc\n- keyword_search: desc"
        mock_registry.return_value = mock_registry_instance

        mock_llm_instance = MagicMock()
        mock_llm_instance.agenerate_structured = AsyncMock(return_value=[
            {"task_id": "t1", "tools": ["semantic_search"]},
            {"task_id": "t2", "tools": ["kg_search", "semantic_search"]},
        ])
        mock_llm.return_value = mock_llm_instance

        state = _make_state([
            {"id": "t1", "description": "find fact", "intent": "fact", "depends_on": [], "status": "pending"},
            {"id": "t2", "description": "find relation", "intent": "relation", "depends_on": [], "status": "pending"},
        ])
        result = await route_node(state)
        assert result["routes"]["t1"] == ["semantic_search"]
        assert result["routes"]["t2"] == ["kg_search", "semantic_search"]


@pytest.mark.asyncio
async def test_router_llm_failure_falls_back_to_rules():
    with patch("app.agents.router.OpenAILLM") as mock_llm, \
         patch("app.agents.router.get_tool_registry") as mock_registry:

        mock_registry_instance = MagicMock()
        mock_registry_instance.tool_names = ["semantic_search", "kg_search", "keyword_search"]
        mock_registry_instance.tool_descriptions = "- semantic_search: desc"
        mock_registry.return_value = mock_registry_instance

        mock_llm_instance = MagicMock()
        mock_llm_instance.agenerate_structured = AsyncMock(side_effect=Exception("LLM dead"))
        mock_llm.return_value = mock_llm_instance

        state = _make_state([
            {"id": "t1", "description": "find fact", "intent": "fact", "depends_on": [], "status": "pending"},
        ])
        result = await route_node(state)
        assert result["routes"]["t1"] == FALLBACK_RULES["fact"]


@pytest.mark.asyncio
async def test_router_filters_invalid_tool_names():
    with patch("app.agents.router.OpenAILLM") as mock_llm, \
         patch("app.agents.router.get_tool_registry") as mock_registry:

        mock_registry_instance = MagicMock()
        mock_registry_instance.tool_names = ["semantic_search"]
        mock_registry_instance.tool_descriptions = "- semantic_search: desc"
        mock_registry.return_value = mock_registry_instance

        mock_llm_instance = MagicMock()
        mock_llm_instance.agenerate_structured = AsyncMock(return_value=[
            {"task_id": "t1", "tools": ["semantic_search", "nonexistent_tool"]},
        ])
        mock_llm.return_value = mock_llm_instance

        state = _make_state([
            {"id": "t1", "description": "find fact", "intent": "fact", "depends_on": [], "status": "pending"},
        ])
        result = await route_node(state)
        assert result["routes"]["t1"] == ["semantic_search"]


@pytest.mark.asyncio
async def test_router_empty_subtasks():
    with patch("app.agents.router.get_tool_registry") as mock_registry:
        mock_registry_instance = MagicMock()
        mock_registry_instance.tool_names = ["semantic_search"]
        mock_registry.return_value = mock_registry_instance

        state = _make_state([])
        result = await route_node(state)
        assert result["routes"] == {}


@pytest.mark.asyncio
async def test_fallback_rules_cover_all_intents():
    for intent in ["fact", "relation", "exact", "comparison", "reasoning"]:
        assert intent in FALLBACK_RULES
        assert len(FALLBACK_RULES[intent]) > 0
```

Run: `pytest tests/unit/agents/test_router.py -v`
Expected: 5 FAIL (old router still in place)

- [ ] **Step 2: Rewrite Router**

```python
# app/agents/router.py
import json
from app.agents.state import AgentState
from app.adapters.llm.openai import OpenAILLM
from app.tools import get_tool_registry

ROUTE_PROMPT = """You are a retrieval routing specialist. Based on each subtask's description and intent, decide which retrieval tools to use.

Available tools:
{tool_descriptions}

Routing guidelines:
- "fact" intent prioritizes semantic_search
- "relation" intent prioritizes kg_search
- "exact" intent prioritizes keyword_search
- "comparison" intent typically needs semantic_search + kg_search
- "reasoning" intent may need all three tools

Sub-tasks:
{tasks_json}

Output JSON array only:
[{{"task_id": "t1", "tools": ["semantic_search"]}}, ...]
"""

FALLBACK_RULES: dict[str, list[str]] = {
    "fact": ["semantic_search"],
    "relation": ["kg_search"],
    "exact": ["keyword_search"],
    "comparison": ["semantic_search", "kg_search"],
    "reasoning": ["semantic_search", "kg_search", "keyword_search"],
}

ROUTE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "tools": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["task_id", "tools"],
    },
}


async def route_node(state: AgentState) -> AgentState:
    tasks = state.get("sub_tasks", [])
    if not tasks:
        state["routes"] = {}
        return state

    registry = get_tool_registry()
    prompt = ROUTE_PROMPT.format(
        tool_descriptions=registry.tool_descriptions,
        tasks_json=json.dumps([
            {"id": t["id"], "description": t["description"], "intent": t["intent"]}
            for t in tasks
        ]),
    )

    try:
        llm = OpenAILLM()
        result = await llm.agenerate_structured(
            prompt,
            "You are a retrieval routing specialist.",
            output_schema=ROUTE_SCHEMA,
        )
        routes = {r["task_id"]: r["tools"] for r in result}
    except Exception:
        routes = {
            t["id"]: FALLBACK_RULES.get(t["intent"], ["semantic_search"])
            for t in tasks
        }

    valid = set(registry.tool_names)
    state["routes"] = {
        tid: [t for t in tools if t in valid]
        for tid, tools in routes.items()
    }
    return state
```

Run: `pytest tests/unit/agents/test_router.py -v`
Expected: 5 PASS

- [ ] **Step 3: Commit**

```bash
git add app/agents/router.py tests/unit/agents/test_router.py
git commit -m "feat(sp3): rewrite Router with LLM dynamic routing + fallback + validation"
```

---

### Task 7: Executor rewrite

**Files:**
- Modify: `app/agents/executor.py` (full rewrite)
- Create: `tests/unit/agents/test_executor.py`

- [ ] **Step 1: Write tests for dependency resolver**

```python
# tests/unit/agents/test_executor.py
import pytest
from app.agents.executor import _resolve_groups


class TestResolveGroups:
    def test_no_dependencies_all_parallel(self):
        sub_tasks = [
            {"id": "t1", "depends_on": []},
            {"id": "t2", "depends_on": []},
        ]
        groups = _resolve_groups(sub_tasks)
        assert groups == [["t1", "t2"]]

    def test_linear_dependency_two_groups(self):
        sub_tasks = [
            {"id": "t1", "depends_on": []},
            {"id": "t2", "depends_on": ["t1"]},
        ]
        groups = _resolve_groups(sub_tasks)
        assert groups == [["t1"], ["t2"]]

    def test_diamond_dependency(self):
        sub_tasks = [
            {"id": "t1", "depends_on": []},
            {"id": "t2", "depends_on": ["t1"]},
            {"id": "t3", "depends_on": ["t1"]},
            {"id": "t4", "depends_on": ["t2", "t3"]},
        ]
        groups = _resolve_groups(sub_tasks)
        assert groups == [["t1"], ["t2", "t3"], ["t4"]]

    def test_circular_dependency_raises(self):
        sub_tasks = [
            {"id": "t1", "depends_on": ["t2"]},
            {"id": "t2", "depends_on": ["t1"]},
        ]
        with pytest.raises(ValueError, match="Circular dependency"):
            _resolve_groups(sub_tasks)

    def test_unknown_dependency_raises(self):
        sub_tasks = [
            {"id": "t1", "depends_on": ["nonexistent"]},
        ]
        with pytest.raises(ValueError, match="depends on unknown task"):
            _resolve_groups(sub_tasks)

    def test_empty_list(self):
        groups = _resolve_groups([])
        assert groups == []
```

Run: `pytest tests/unit/agents/test_executor.py::TestResolveGroups -v`
Expected: FAIL — `_resolve_groups` not defined

- [ ] **Step 2: Implement _resolve_groups**

Create `app/agents/executor.py` with the resolver first:

```python
# app/agents/executor.py
from app.agents.state import AgentState, RetrievedChunk


def _resolve_groups(sub_tasks: list[dict]) -> list[list[str]]:
    """Topological sort into execution groups. Tasks within a group have no mutual dependencies."""
    if not sub_tasks:
        return []

    all_ids = {t["id"] for t in sub_tasks}
    for t in sub_tasks:
        for dep in t.get("depends_on", []):
            if dep not in all_ids:
                raise ValueError(f"Task {t['id']} depends on unknown task {dep}")

    completed: set[str] = set()
    remaining = {t["id"]: set(t.get("depends_on", [])) for t in sub_tasks}
    groups: list[list[str]] = []

    while remaining:
        ready = [tid for tid, deps in remaining.items() if deps.issubset(completed)]
        if not ready:
            raise ValueError(f"Circular dependency detected: {remaining}")
        groups.append(ready)
        completed.update(ready)
        for tid in ready:
            del remaining[tid]

    return groups
```

Run: `pytest tests/unit/agents/test_executor.py::TestResolveGroups -v`
Expected: 6 PASS

- [ ] **Step 3: Commit**

```bash
git add app/agents/executor.py tests/unit/agents/test_executor.py
git commit -m "feat(sp3): add _resolve_groups — topological sort for task dependencies"
```

- [ ] **Step 4: Write failing tests for executor integration**

Add to `tests/unit/agents/test_executor.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.state import AgentState
from app.agents.executor import executor_node


def _make_state(sub_tasks=None, routes=None, collection_ids=None):
    state: AgentState = {
        "query": "test", "conversation_history": [],
        "intent": "", "rewritten_query": "",
        "sub_tasks": sub_tasks or [],
        "routes": routes or {},
        "retrieved": [], "raw_milvus_hits": [], "raw_kg_results": [], "raw_keyword_hits": [],
        "reflection_notes": "", "missing_info": [], "quality_score": 0.0, "need_another_round": False,
        "draft_answer": "", "verified_claims": [], "supplement_queries": [], "need_supplement": False,
        "final_answer": "", "citations": [], "uncertainty_flags": [], "warnings": [], "bare_minimum_mode": False,
        "iteration": 0, "max_iterations": 5, "prev_score": None, "collection_ids": collection_ids or ["col1"],
    }
    return state


@pytest.mark.asyncio
async def test_executor_single_tool_success():
    with patch("app.agents.executor.get_tool_registry") as mock_registry:
        mock_tool = MagicMock()
        mock_tool.arun = AsyncMock(return_value=[
            {"chunk_id": "c1", "document_id": "d1", "text": "hello", "score": 0.9, "source": "milvus"},
        ])
        mock_registry_instance = MagicMock()
        mock_registry_instance.get.return_value = mock_tool
        mock_registry.return_value = mock_registry_instance

        state = _make_state(
            sub_tasks=[{"id": "t1", "description": "find", "intent": "fact", "depends_on": [], "status": "pending"}],
            routes={"t1": ["semantic_search"]},
        )
        result = await executor_node(state)
        assert len(result["retrieved"]) == 1
        assert result["retrieved"][0].chunk_id == "c1"
        assert len(result["raw_milvus_hits"]) == 1
        assert len(result["raw_kg_results"]) == 0
        assert len(result["raw_keyword_hits"]) == 0


@pytest.mark.asyncio
async def test_executor_tool_failure_isolated():
    with patch("app.agents.executor.get_tool_registry") as mock_registry:
        mock_tool_success = MagicMock()
        mock_tool_success.arun = AsyncMock(return_value=[
            {"chunk_id": "c1", "document_id": "d1", "text": "ok", "score": 0.9, "source": "milvus"},
        ])
        mock_tool_fail = MagicMock()
        mock_tool_fail.arun = AsyncMock(side_effect=Exception("Tool error"))

        mock_registry_instance = MagicMock()
        mock_registry_instance.get.side_effect = lambda name: {
            "semantic_search": mock_tool_success,
            "kg_search": mock_tool_fail,
        }[name]
        mock_registry.return_value = mock_registry_instance

        state = _make_state(
            sub_tasks=[{"id": "t1", "description": "find", "intent": "reasoning", "depends_on": [], "status": "pending"}],
            routes={"t1": ["semantic_search", "kg_search"]},
        )
        result = await executor_node(state)
        assert len(result["retrieved"]) == 1
        assert len(result["warnings"]) == 1
        assert "kg_search" in result["warnings"][0]


@pytest.mark.asyncio
async def test_executor_deduplicates_by_chunk_id():
    with patch("app.agents.executor.get_tool_registry") as mock_registry:
        mock_tool = MagicMock()
        mock_tool.arun = AsyncMock(return_value=[
            {"chunk_id": "c1", "document_id": "d1", "text": "hello", "score": 0.9, "source": "milvus"},
            {"chunk_id": "c1", "document_id": "d1", "text": "hello", "score": 0.7, "source": "keyword"},
        ])
        mock_registry_instance = MagicMock()
        mock_registry_instance.get.return_value = mock_tool
        mock_registry.return_value = mock_registry_instance

        state = _make_state(
            sub_tasks=[{"id": "t1", "description": "find", "intent": "fact", "depends_on": [], "status": "pending"}],
            routes={"t1": ["semantic_search", "keyword_search"]},
        )
        result = await executor_node(state)
        assert len(result["retrieved"]) == 1
        assert result["retrieved"][0].score == 0.9


@pytest.mark.asyncio
async def test_executor_empty_subtasks_returns_empty():
    state = _make_state(sub_tasks=[], routes={})
    result = await executor_node(state)
    assert result["retrieved"] == []
    assert result["warnings"] == []


@pytest.mark.asyncio
async def test_executor_subtask_status_updated():
    with patch("app.agents.executor.get_tool_registry") as mock_registry:
        mock_tool = MagicMock()
        mock_tool.arun = AsyncMock(return_value=[
            {"chunk_id": "c1", "document_id": "d1", "text": "ok", "score": 0.9, "source": "milvus"},
        ])
        mock_registry_instance = MagicMock()
        mock_registry_instance.get.return_value = mock_tool
        mock_registry.return_value = mock_registry_instance

        state = _make_state(
            sub_tasks=[{"id": "t1", "description": "find", "intent": "fact", "depends_on": [], "status": "pending"}],
            routes={"t1": ["semantic_search"]},
        )
        result = await executor_node(state)
        assert result["sub_tasks"][0]["status"] == "done"


@pytest.mark.asyncio
async def test_executor_subtask_all_tools_fail():
    with patch("app.agents.executor.get_tool_registry") as mock_registry:
        mock_tool = MagicMock()
        mock_tool.arun = AsyncMock(side_effect=Exception("All dead"))
        mock_registry_instance = MagicMock()
        mock_registry_instance.get.return_value = mock_tool
        mock_registry.return_value = mock_registry_instance

        state = _make_state(
            sub_tasks=[{"id": "t1", "description": "find", "intent": "fact", "depends_on": [], "status": "pending"}],
            routes={"t1": ["semantic_search"]},
        )
        result = await executor_node(state)
        assert result["sub_tasks"][0]["status"] == "failed"
        assert result["retrieved"] == []
```

Run: `pytest tests/unit/agents/test_executor.py -v -k "test_executor"`
Expected: FAIL — `executor_node` still missing or old version

- [ ] **Step 5: Complete the executor rewrite**

Complete `app/agents/executor.py`:

```python
import asyncio
from app.agents.state import AgentState, RetrievedChunk
from app.tools import get_tool_registry


def _resolve_groups(sub_tasks: list[dict]) -> list[list[str]]:
    if not sub_tasks:
        return []

    all_ids = {t["id"] for t in sub_tasks}
    for t in sub_tasks:
        for dep in t.get("depends_on", []):
            if dep not in all_ids:
                raise ValueError(f"Task {t['id']} depends on unknown task {dep}")

    completed: set[str] = set()
    remaining = {t["id"]: set(t.get("depends_on", [])) for t in sub_tasks}
    groups: list[list[str]] = []

    while remaining:
        ready = [tid for tid, deps in remaining.items() if deps.issubset(completed)]
        if not ready:
            raise ValueError(f"Circular dependency detected: {remaining}")
        groups.append(ready)
        completed.update(ready)
        for tid in ready:
            del remaining[tid]

    return groups


async def _execute_task(
    task: dict,
    routes: dict[str, list[str]],
    collection_ids: list[str],
    registry,
) -> tuple[list[dict], list[str]]:
    tool_names = routes.get(task["id"], ["semantic_search"])
    task["status"] = "running"
    warnings: list[str] = []

    results = await asyncio.gather(*[
        registry.get(name).arun(task["description"], collection_ids)
        for name in tool_names
    ], return_exceptions=True)

    hits: list[dict] = []
    for name, result in zip(tool_names, results):
        if isinstance(result, Exception):
            warnings.append(f"Tool {name} failed: {result}")
        else:
            for item in result:
                item["_tool"] = name
            hits.extend(result)

    task["status"] = "failed" if not hits else "done"
    return hits, warnings


async def executor_node(state: AgentState) -> AgentState:
    sub_tasks = state.get("sub_tasks", [])
    routes = state.get("routes", {})
    collection_ids = state.get("collection_ids", [])

    state["raw_milvus_hits"] = []
    state["raw_kg_results"] = []
    state["raw_keyword_hits"] = []
    warnings: list[str] = []

    if not sub_tasks:
        state["retrieved"] = []
        state["warnings"] = warnings
        return state

    registry = get_tool_registry()

    try:
        groups = _resolve_groups(sub_tasks)
    except ValueError as e:
        if "depends on unknown" in str(e):
            groups = [[t["id"]] for t in sub_tasks]
            warnings.append(f"Dependency resolution skipped: {e}")
        else:
            raise

    all_hits: list[dict] = []
    for group in groups:
        group_tasks = [t for t in sub_tasks if t["id"] in group]
        group_results = await asyncio.gather(*[
            _execute_task(t, routes, collection_ids, registry)
            for t in group_tasks
        ])
        for hits, warns in group_results:
            all_hits.extend(hits)
            warnings.extend(warns)

    retrieved: list[RetrievedChunk] = []
    seen: set[str] = set()
    for hit in sorted(all_hits, key=lambda h: h["score"], reverse=True):
        if hit["chunk_id"] not in seen:
            retrieved.append(RetrievedChunk(
                chunk_id=hit["chunk_id"],
                document_id=hit.get("document_id", ""),
                text=hit["text"],
                score=hit["score"],
                source=hit["source"],
                metadata={},
            ))
            seen.add(hit["chunk_id"])

    state["retrieved"] = retrieved
    state["raw_milvus_hits"] = [h for h in all_hits if h["_tool"] == "semantic_search"]
    state["raw_kg_results"] = [h for h in all_hits if h["_tool"] == "kg_search"]
    state["raw_keyword_hits"] = [h for h in all_hits if h["_tool"] == "keyword_search"]
    state.setdefault("warnings", []).extend(warnings)
    return state
```

Run: `pytest tests/unit/agents/test_executor.py -v`
Expected: 12 PASS (6 resolver + 6 integration)

- [ ] **Step 6: Commit**

```bash
git add app/agents/executor.py tests/unit/agents/test_executor.py
git commit -m "feat(sp3): rewrite Executor — dependency resolution + parallel dispatch + normalization"
```

---

### Task 8: agent_service.py adapt

**Files:**
- Modify: `app/services/agent_service.py:53-55`

- [ ] **Step 1: Fix routes_used flattening**

In `app/services/agent_service.py`, change lines 53-55:

```python
# Before:
        "routes_used": list(set(result.get("routes", {}").values())),
# After:
        routes = result.get("routes", {})
        flat: set[str] = set()
        for tools in routes.values():
            flat.update(tools)
        routes_used = list(flat),
```

- [ ] **Step 2: Verify syntax**

Run: `python -c "import ast; ast.parse(open('app/services/agent_service.py').read()); print('Syntax OK')"`

- [ ] **Step 3: Commit**

```bash
git add app/services/agent_service.py
git commit -m "fix(sp3): flatten routes_used for new list[str] routes format"
```

---

### Task 9: test_all_imports extension

**Files:**
- Modify: `tests/unit/ingestion/test_all_imports.py`

- [ ] **Step 1: Add SP3 import tests**

Add to `tests/unit/ingestion/test_all_imports.py`:

```python
def test_import_base_tool():
    from app.tools.base import BaseTool
    assert BaseTool is not None


def test_import_tool_registry():
    from app.tools import ToolRegistry, get_tool_registry
    assert ToolRegistry is not None
    assert get_tool_registry is not None


def test_import_semantic_search_tool():
    from app.tools.semantic_search import SemanticSearchTool
    assert SemanticSearchTool is not None


def test_import_kg_search_tool():
    from app.tools.kg_search import KGSearchTool
    assert KGSearchTool is not None


def test_import_keyword_search_tool():
    from app.tools.keyword_search import KeywordSearchTool
    assert KeywordSearchTool is not None


def test_import_router_fallback_rules():
    from app.agents.router import FALLBACK_RULES
    assert FALLBACK_RULES is not None


def test_import_executor_resolve_groups():
    from app.agents.executor import _resolve_groups
    assert _resolve_groups is not None
```

Run: `pytest tests/unit/ingestion/test_all_imports.py -v`
Expected: 14 PASS (7 original + 7 new)

- [ ] **Step 2: Commit**

```bash
git add tests/unit/ingestion/test_all_imports.py
git commit -m "test(sp3): extend import verification to app/tools/ + new agent functions"
```

---

### Task 10: Full regression

**Files:**
- All SP3 files (verify)

- [ ] **Step 1: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests PASS. Target: ~69 tests (35 SP2 + 10 Phase 1 + 24 SP3)

- [ ] **Step 2: Verify FastAPI app loads**

```bash
python -c "from app.main import app; print('FastAPI app loaded OK')"
```

Expected: FastAPI app loaded OK

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "test(sp3): full regression — all tests passing"
```

---

## Summary

| Phase | Tasks | Files Created | Files Modified |
|-------|-------|---------------|----------------|
| Foundation | 1 | `app/tools/base.py`, `app/tools/__init__.py` | — |
| Tools | 2-4 | `semantic_search.py`, `kg_search.py`, `keyword_search.py` | — |
| State | 5 | — | `app/agents/state.py` (1 line) |
| Router | 6 | — | `app/agents/router.py` (rewrite) |
| Executor | 7 | — | `app/agents/executor.py` (rewrite) |
| Service | 8 | — | `app/services/agent_service.py` (1 line) |
| Tests | 9 | — | `test_all_imports.py` (extend) |
| Verify | 10 | — | — |

**Total: 5 new files, 4 modified files, 10 commits, ~69 tests passing**