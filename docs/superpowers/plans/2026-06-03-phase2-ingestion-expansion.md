# Phase 2 SP2: 摄入扩展 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扩展摄入管道从单路径(仅 semantic_path→Milvus)到三路并行(semantic + graph + keyword)，新增 WebSource 和 DBSource，添加修复队列

**Architecture:** 自底向上构建 — 先装依赖 → 各路径模块独立实现 → 新 sources → 改造 pipeline fork → repair worker → workers 集成 → 集成测试

**Tech Stack:** Python 3.12, jieba (中文分词), BeautifulSoup4 (HTML 解析), httpx (HTTP), SQLAlchemy (DB 连接), Neo4j, Elasticsearch, ARQ

**Spec:** docs/superpowers/specs/2026-06-03-phase2-ingestion-expansion-design.md

---

### Task 1: 安装新依赖

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 添加 jieba 和 beautifulsoup4 到 pyproject.toml**

在 `pyproject.toml` 的 dependencies 列表末尾（`"pgvector>=0.2.0",` 之后）追加：

```toml
    "jieba>=0.42.1",
    "beautifulsoup4>=4.12.0",
```

- [ ] **Step 2: 安装依赖**

Run: `pip install jieba>=0.42.1 beautifulsoup4>=4.12.0`
Expected: 两个包安装成功

- [ ] **Step 3: 验证安装**

```bash
python -c "import jieba; list(jieba.cut('测试分词')); print('OK')"
python -c "from bs4 import BeautifulSoup; print('OK')"
```

Expected: 两次输出 "OK"

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add jieba and beautifulsoup4 dependencies for SP2"
```

---

### Task 2: graph_path/__init__.py + entity_extractor (jieba + TF-IDF)

**Files:**
- Create: `app/ingestion/graph_path/__init__.py`
- Create: `app/ingestion/graph_path/entity_extractor.py`
- Create: `tests/unit/ingestion/__init__.py`
- Create: `tests/unit/ingestion/test_entity_extractor.py`

- [ ] **Step 1: 创建目录和 __init__.py**

```bash
mkdir -p app/ingestion/graph_path
mkdir -p app/ingestion/keyword_path
mkdir -p tests/unit/ingestion
```

```python
# app/ingestion/graph_path/__init__.py (empty)
```

```python
# app/ingestion/keyword_path/__init__.py (empty)
```

```python
# tests/unit/ingestion/__init__.py (empty)
```

- [ ] **Step 2: 写失败测试 — test_entity_extractor.py**

```python
# tests/unit/ingestion/test_entity_extractor.py
import pytest
from app.ingestion.graph_path.entity_extractor import extract_candidate_entities


def test_extract_basic_nouns():
    text = "阿里巴巴集团成立于1999年，总部位于杭州，创始人马云。"
    entities = extract_candidate_entities(text, top_k=10)

    assert isinstance(entities, list)
    assert len(entities) > 0
    assert all("name" in e and "score" in e and "type" in e for e in entities)
    names = [e["name"] for e in entities]
    assert any("杭州" in n for n in names) or any("阿里巴巴" in n for n in names)


def test_filter_non_nouns():
    text = "的 了 在 是 和 很 都 也 就 把"
    entities = extract_candidate_entities(text, top_k=10)
    assert len(entities) == 0


def test_empty_text():
    entities = extract_candidate_entities("", top_k=10)
    assert entities == []


def test_returns_top_k():
    text = """
    机器学习是人工智能的一个分支。深度神经网络在图像识别、自然语言处理和
    语音识别等领域取得了突破性进展。卷积神经网络和循环神经网络是两种常见架构。
    谷歌、微软、百度等公司投入大量资源研发。PyTorch和TensorFlow是主流框架。
    """
    entities = extract_candidate_entities(text, top_k=5)
    assert len(entities) <= 5
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/unit/ingestion/test_entity_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingestion.graph_path.entity_extractor'`

- [ ] **Step 4: 实现 entity_extractor.py**

```python
# app/ingestion/graph_path/entity_extractor.py
from collections import Counter
import math
import jieba.posseg as pseg

_POS_TYPE_MAP = {
    "n": "concept",
    "nr": "person",
    "ns": "location",
    "nt": "organization",
    "nz": "term",
}

_KEEP_POS = set(_POS_TYPE_MAP.keys())

_STOP_WORDS = {
    "文档", "页面", "文件", "部分", "内容", "信息", "数据",
    "问题", "方法", "方式", "过程", "结果", "情况", "方面",
    "时间", "系统", "用户", "功能", "使用", "可以", "需要",
}


def extract_candidate_entities(text: str, top_k: int = 50) -> list[dict]:
    """从文本中提取候选实体（jieba 分词 + TF-IDF 加权）。

    Args:
        text: 输入文本
        top_k: 返回的候选实体数量上限

    Returns:
        [{"name": str, "score": float, "type": str}, ...]
    """
    if not text or not text.strip():
        return []

    words = list(pseg.cut(text))

    nouns = [
        (w.word, w.flag)
        for w in words
        if w.flag in _KEEP_POS and len(w.word) >= 2 and w.word not in _STOP_WORDS
    ]

    if not nouns:
        return []

    word_counts = Counter(w[0] for w in nouns)

    seen = {}
    for word, flag in nouns:
        if word not in seen:
            seen[word] = flag

    total = sum(word_counts.values())
    doc_count = len(word_counts)

    scored = []
    for word, count in word_counts.items():
        tf = count / total
        idf = math.log((doc_count + 1) / (count + 1)) + 1
        score = tf * idf
        scored.append((word, score, seen[word]))

    scored.sort(key=lambda x: x[1], reverse=True)

    return [
        {"name": word, "score": round(score, 4), "type": _POS_TYPE_MAP.get(flag, "concept")}
        for word, score, flag in scored[:top_k]
    ]
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/unit/ingestion/test_entity_extractor.py -v`
Expected: 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/ingestion/graph_path/__init__.py app/ingestion/graph_path/entity_extractor.py tests/unit/ingestion/__init__.py tests/unit/ingestion/test_entity_extractor.py
git commit -m "feat: add jieba+TF-IDF entity extractor for graph_path"
```

---

### Task 3: graph_path/relation_extractor (LLM 消歧 + 关系提取)

**Files:**
- Create: `app/ingestion/graph_path/relation_extractor.py`
- Create: `tests/unit/ingestion/test_relation_extractor.py`

- [ ] **Step 1: 写失败测试 — test_relation_extractor.py**

```python
# tests/unit/ingestion/test_relation_extractor.py
import pytest
from unittest.mock import AsyncMock
from app.ingestion.graph_path.relation_extractor import extract_relations, RELATION_SCHEMA


def test_relation_schema_has_required_fields():
    schema = RELATION_SCHEMA
    assert "entities" in schema["properties"]
    assert "relations" in schema["properties"]
    entity_props = schema["properties"]["entities"]["items"]["properties"]
    assert "id" in entity_props
    assert "name" in entity_props
    assert "type" in entity_props
    assert "aliases" in entity_props
    rel_props = schema["properties"]["relations"]["items"]["properties"]
    assert "from_entity" in rel_props
    assert "to_entity" in rel_props
    assert "type" in rel_props


@pytest.mark.asyncio
async def test_extract_relations_mock_llm():
    mock_llm = AsyncMock()
    mock_llm.agenerate_structured.return_value = {
        "entities": [
            {"id": "e1", "name": "阿里巴巴", "type": "organization", "aliases": ["阿里"]},
            {"id": "e2", "name": "杭州", "type": "location", "aliases": []},
        ],
        "relations": [
            {"from_entity": "e1", "to_entity": "e2", "type": "LOCATED_IN"},
        ],
    }

    entities = [
        {"name": "阿里巴巴", "score": 0.8, "type": "organization"},
        {"name": "杭州", "score": 0.6, "type": "location"},
    ]
    text = "阿里巴巴总部位于杭州。"

    result = await extract_relations(text, entities, mock_llm)

    assert "entities" in result
    assert "relations" in result
    assert len(result["entities"]) == 2
    assert len(result["relations"]) == 1
    mock_llm.agenerate_structured.assert_called_once()


@pytest.mark.asyncio
async def test_extract_relations_empty_entities():
    mock_llm = AsyncMock()
    mock_llm.agenerate_structured.return_value = {"entities": [], "relations": []}

    result = await extract_relations("some text", [], mock_llm)
    assert result["entities"] == []
    assert result["relations"] == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/ingestion/test_relation_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 relation_extractor.py**

```python
# app/ingestion/graph_path/relation_extractor.py
import json

RELATION_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": ["person", "location", "organization", "concept", "term"]},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "name", "type", "aliases"],
            },
        },
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from_entity": {"type": "string"},
                    "to_entity": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["RELATED_TO", "PART_OF", "DEPENDS_ON", "PRODUCES", "DESCRIBES", "LOCATED_IN"],
                    },
                },
                "required": ["from_entity", "to_entity", "type"],
            },
        },
    },
    "required": ["entities", "relations"],
}


async def extract_relations(text: str, entities: list[dict], llm) -> dict:
    """用 LLM 对候选实体进行消歧并提取关系。

    Args:
        text: 原始文本（截断到 3000 字）
        entities: 候选实体列表 [{"name", "score", "type"}, ...]
        llm: BaseLLM 实例（用于 agenerate_structured）

    Returns:
        {"entities": [...], "relations": [...]}
    """
    if not entities:
        return {"entities": [], "relations": []}

    truncated = text[:3000]
    entity_json = json.dumps(entities, ensure_ascii=False)

    prompt = f"""文本:
{truncated}

候选实体:
{entity_json}

任务:
1. 对候选实体进行消歧：同名不同义拆分为不同实体，同义不同名合并为一个实体（aliases 列出别名）
2. 提取实体之间的语义关系

返回符合 schema 的 JSON。"""

    system_prompt = "你是一个知识图谱构建专家。仔细分析文本，准确提取实体和关系。"

    return await llm.agenerate_structured(
        prompt,
        system_prompt=system_prompt,
        output_schema=RELATION_SCHEMA,
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/ingestion/test_relation_extractor.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/ingestion/graph_path/relation_extractor.py tests/unit/ingestion/test_relation_extractor.py
git commit -m "feat: add LLM-based relation extractor for graph_path"
```

---

### Task 4: graph_path/neo4j_writer (写 Neo4j)

**Files:**
- Create: `app/ingestion/graph_path/neo4j_writer.py`
- Create: `tests/unit/ingestion/test_neo4j_writer.py`

- [ ] **Step 1: 写失败测试 — test_neo4j_writer.py**

```python
# tests/unit/ingestion/test_neo4j_writer.py
import pytest
from unittest.mock import AsyncMock
from app.ingestion.graph_path.neo4j_writer import write_graph_to_neo4j


@pytest.mark.asyncio
async def test_write_graph_to_neo4j():
    mock_store = AsyncMock()
    mock_store.acreate_graph.return_value = None

    entities = [
        {"id": "e1", "name": "阿里巴巴", "type": "organization", "aliases": ["阿里"]},
    ]
    relations = [
        {"from_entity": "e1", "to_entity": "e2", "type": "LOCATED_IN"},
    ]

    await write_graph_to_neo4j("doc_001", entities, relations, mock_store)

    mock_store.acreate_graph.assert_called_once_with(
        "doc_001", entities, relations
    )


@pytest.mark.asyncio
async def test_write_graph_empty_lists():
    mock_store = AsyncMock()
    await write_graph_to_neo4j("doc_001", [], [], mock_store)
    mock_store.acreate_graph.assert_called_once_with("doc_001", [], [])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/ingestion/test_neo4j_writer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 neo4j_writer.py**

```python
# app/ingestion/graph_path/neo4j_writer.py


async def write_graph_to_neo4j(
    doc_id: str, entities: list[dict], relations: list[dict], kg_store
) -> None:
    """将实体和关系写入 Neo4j 知识图谱。

    Args:
        doc_id: 文档 ID
        entities: 消歧后的实体列表 [{"id", "name", "type", "aliases"}, ...]
        relations: 关系列表 [{"from_entity", "to_entity", "type"}, ...]
        kg_store: Neo4jKGStore 实例
    """
    await kg_store.acreate_graph(doc_id, entities, relations)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/ingestion/test_neo4j_writer.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/ingestion/graph_path/neo4j_writer.py tests/unit/ingestion/test_neo4j_writer.py
git commit -m "feat: add Neo4j writer for graph_path"
```

---

### Task 5: keyword_path/es_writer (全文档 ES 写入)

**Files:**
- Create: `app/ingestion/keyword_path/es_writer.py`
- Create: `tests/unit/ingestion/test_es_writer.py`

- [ ] **Step 1: 写失败测试 — test_es_writer.py**

```python
# tests/unit/ingestion/test_es_writer.py
import pytest
from unittest.mock import AsyncMock
from app.ingestion.keyword_path.es_writer import write_document_to_es


@pytest.mark.asyncio
async def test_write_document_to_es():
    mock_store = AsyncMock()
    mock_store.aindex_document.return_value = None

    await write_document_to_es(
        doc_id="doc_001",
        collection_id="col_123",
        title="测试文档",
        content="这是文档的完整内容，不会被分块。",
        metadata={"source_type": "local", "source_path": "/tmp/test.md"},
        search_store=mock_store,
    )

    mock_store.aindex_document.assert_called_once()
    call_args = mock_store.aindex_document.call_args
    assert call_args[0][0] == "col_123"
    assert call_args[0][1] == "doc_001"
    assert call_args[0][2] == "测试文档"
    assert call_args[0][3] == "这是文档的完整内容，不会被分块。"


@pytest.mark.asyncio
async def test_write_document_passes_metadata():
    mock_store = AsyncMock()
    mock_store.aindex_document.return_value = None

    metadata = {
        "source_type": "web",
        "source_path": "https://example.com/article",
        "mime_type": "text/html",
        "language": "zh",
        "page_number": None,
    }

    await write_document_to_es(
        doc_id="doc_002",
        collection_id="col_456",
        title="Web Article",
        content="Full content here.",
        metadata=metadata,
        search_store=mock_store,
    )

    passed_metadata = mock_store.aindex_document.call_args[0][4]
    assert passed_metadata["source_type"] == "web"
    assert passed_metadata["source_path"] == "https://example.com/article"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/ingestion/test_es_writer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 es_writer.py**

```python
# app/ingestion/keyword_path/es_writer.py


async def write_document_to_es(
    doc_id: str,
    collection_id: str,
    title: str,
    content: str,
    metadata: dict,
    search_store,
) -> None:
    """将完整文档写入 Elasticsearch（不分块）。

    Args:
        doc_id: 文档 ID
        collection_id: 知识库 ID
        title: 文档标题
        content: 完整文档内容（不分块）
        metadata: 文档元数据 (source_type, source_path, mime_type, language, page_number 等)
        search_store: ElasticsearchStore 实例
    """
    await search_store.aindex_document(
        collection_id, doc_id, title, content, metadata
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/ingestion/test_es_writer.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/ingestion/keyword_path/es_writer.py tests/unit/ingestion/test_es_writer.py
git commit -m "feat: add ES writer for keyword_path (full document)"
```

---

### Task 6: WebSource (httpx + BeautifulSoup)

**Files:**
- Create: `app/ingestion/sources/web.py`
- Create: `tests/unit/ingestion/test_web_source.py`

- [ ] **Step 1: 写失败测试 — test_web_source.py**

```python
# tests/unit/ingestion/test_web_source.py
import pytest
import os
import tempfile
from unittest.mock import AsyncMock, patch
from app.ingestion.sources.web import WebSource


@pytest.mark.asyncio
async def test_web_source_list_files_no_urls():
    source = WebSource(urls=[])
    files = await source.list_files()
    assert files == []


def test_extract_text_removes_noise_tags():
    html = """
    <html><head><script>alert('x')</script><style>body{}</style></head>
    <body>
        <nav>导航</nav>
        <header>页头</header>
        <main><p>正文内容在这里</p></main>
        <footer>页脚</footer>
        <aside>侧栏</aside>
    </body></html>
    """
    source = WebSource(urls=["http://example.com"])
    text = source._extract_text(html)

    assert "正文内容在这里" in text
    assert "导航" not in text
    assert "页头" not in text
    assert "页脚" not in text
    assert "侧栏" not in text
    assert "alert" not in text


def test_extract_text_empty_html():
    source = WebSource(urls=["http://example.com"])
    text = source._extract_text("<html></html>")
    assert isinstance(text, str)


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_list_files_fetches_and_saves(mock_get):
    html = "<html><body><p>Hello World</p></body></html>"

    mock_response = AsyncMock()
    mock_response.text = html
    mock_response.raise_for_status = AsyncMock()
    mock_get.return_value = mock_response

    source = WebSource(urls=["http://example.com/test"], tmp_dir=tempfile.gettempdir())
    files = await source.list_files()

    assert len(files) == 1
    assert files[0].endswith(".txt")
    content = await source.get_file_content(files[0])
    assert b"Hello World" in content
    os.remove(files[0])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/ingestion/test_web_source.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 web.py**

```python
# app/ingestion/sources/web.py
import os
import tempfile
import hashlib
import httpx
from bs4 import BeautifulSoup
from app.ingestion.sources.base import BaseSource


class WebSource(BaseSource):
    """Web 摄入源：httpx 获取 + BeautifulSoup 正文提取。"""

    def __init__(self, urls: list[str], max_depth: int = 1, tmp_dir: str | None = None):
        self._urls = urls
        self._max_depth = max_depth
        self._tmp_dir = tmp_dir or tempfile.gettempdir()
        self._saved_files: list[str] = []

    async def list_files(self) -> list[str]:
        """爬取所有 URL，保存为临时 txt 文件，返回文件路径列表。"""
        self._saved_files = []
        for url in self._urls:
            try:
                text = await self._fetch_and_extract(url)
                file_path = self._save_text(text, url)
                self._saved_files.append(file_path)
            except Exception:
                continue
        return self._saved_files

    async def get_file_content(self, file_path: str) -> bytes:
        """读取临时文件的原始内容。"""
        with open(file_path, "rb") as f:
            return f.read()

    async def _fetch_and_extract(self, url: str) -> str:
        """获取 URL 内容并提取正文文本。"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            return self._extract_text(resp.text)

    def _extract_text(self, html: str) -> str:
        """从 HTML 中提取正文，去除噪音标签。"""
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)

    def _save_text(self, text: str, url: str) -> str:
        """保存文本到临时文件。"""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        filename = f"web_{url_hash}.txt"
        file_path = os.path.join(self._tmp_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)
        return file_path
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/ingestion/test_web_source.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/ingestion/sources/web.py tests/unit/ingestion/test_web_source.py
git commit -m "feat: add WebSource (httpx + BeautifulSoup)"
```

---

### Task 7: DBSource (SQLAlchemy 通用连接器)

**Files:**
- Create: `app/ingestion/sources/database.py`
- Create: `tests/unit/ingestion/test_db_source.py`

- [ ] **Step 1: 写失败测试 — test_db_source.py**

```python
# tests/unit/ingestion/test_db_source.py
import pytest
import os
import tempfile
from unittest.mock import MagicMock, patch
from app.ingestion.sources.database import DBSource


def test_row_to_document_basic():
    source = DBSource(
        db_url="sqlite:///test.db",
        query="SELECT * FROM articles",
        title_column="title",
        content_columns=["summary", "body"],
    )

    row = MagicMock()
    row.__getitem__ = lambda self, key: {"title": "Test Title", "summary": "Summary text.", "body": "Full body text."}[key]
    row.get = lambda self, key, default=None: {"title": "Test Title", "summary": "Summary text.", "body": "Full body text."}.get(key, default)

    doc = source._row_to_document(row)
    assert "# Test Title" in doc
    assert "Summary text." in doc
    assert "Full body text." in doc


def test_row_to_document_single_column():
    source = DBSource(
        db_url="sqlite:///test.db",
        query="SELECT * FROM notes",
        title_column="name",
        content_columns=["text"],
    )

    class FakeRow:
        def __getitem__(self, key):
            return {"name": "Note 1", "text": "Just one content column."}[key]
        def get(self, key, default=None):
            return {"name": "Note 1", "text": "Just one content column."}.get(key, default)

    doc = source._row_to_document(FakeRow())
    assert doc == "# Note 1\n\nJust one content column."


def test_row_to_document_null_values():
    source = DBSource(
        db_url="sqlite:///test.db",
        query="SELECT * FROM t",
        title_column="title",
        content_columns=["col1", "col2"],
    )

    class FakeRow:
        def __getitem__(self, key):
            return {"title": "T", "col1": "A", "col2": None}[key]
        def get(self, key, default=None):
            return {"title": "T", "col1": "A", "col2": None}.get(key, default)

    doc = source._row_to_document(FakeRow())
    assert "# T" in doc
    assert "A" in doc
    assert "None" not in doc


@pytest.mark.asyncio
@patch("sqlalchemy.create_engine")
async def test_list_files_executes_query(mock_create_engine):
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_create_engine.return_value = mock_engine
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value = mock_result
    mock_result.mappings.return_value = [
        {"title": "Doc 1", "body": "Content 1"},
        {"title": "Doc 2", "body": "Content 2"},
    ]

    source = DBSource(
        db_url="sqlite:///test.db",
        query="SELECT title, body FROM articles",
        title_column="title",
        content_columns=["body"],
        tmp_dir=tempfile.gettempdir(),
    )

    files = await source.list_files()

    assert len(files) == 2
    assert all(f.endswith(".md") for f in files)

    content = await source.get_file_content(files[0])
    assert b"# Doc 1" in content
    assert b"Content 1" in content

    for f in files:
        os.remove(f)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/ingestion/test_db_source.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 database.py**

```python
# app/ingestion/sources/database.py
import os
import tempfile
import hashlib
from sqlalchemy import create_engine, text
from app.ingestion.sources.base import BaseSource


class DBSource(BaseSource):
    """数据库摄入源：SQLAlchemy 通用连接器，行→文档映射。"""

    def __init__(
        self,
        db_url: str,
        query: str,
        title_column: str,
        content_columns: list[str],
        tmp_dir: str | None = None,
    ):
        self._db_url = db_url
        self._query = query
        self._title_col = title_column
        self._content_cols = content_columns
        self._tmp_dir = tmp_dir or tempfile.gettempdir()
        self._saved_files: list[str] = []

    async def list_files(self) -> list[str]:
        """执行查询，每行保存为临时 md 文件，返回文件路径列表。"""
        engine = create_engine(self._db_url)
        self._saved_files = []

        with engine.connect() as conn:
            result = conn.execute(text(self._query))
            for i, row in enumerate(result.mappings()):
                doc_text = self._row_to_document(row)
                file_path = self._save_text(doc_text, i)
                self._saved_files.append(file_path)

        return self._saved_files

    async def get_file_content(self, file_path: str) -> bytes:
        """读取临时文件的原始内容。"""
        with open(file_path, "rb") as f:
            return f.read()

    def _row_to_document(self, row) -> str:
        """将一行数据转为结构化 Markdown 文本。

        格式: # {title}\n\n{col1_content}\n\n{col2_content}...
        """
        title = row[self._title_col] or ""
        parts = [f"# {title}"]

        for col in self._content_cols:
            value = row.get(col)
            if value is not None:
                parts.append(str(value))

        return "\n\n".join(parts)

    def _save_text(self, text: str, index: int) -> str:
        """保存文本到临时文件。"""
        content_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        filename = f"db_{index}_{content_hash}.md"
        file_path = os.path.join(self._tmp_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)
        return file_path
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/ingestion/test_db_source.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/ingestion/sources/database.py tests/unit/ingestion/test_db_source.py
git commit -m "feat: add DBSource (SQLAlchemy generic connector)"
```

---

### Task 8: 更新 sources/__init__.py

**Files:**
- Modify: `app/ingestion/sources/__init__.py`

- [ ] **Step 1: 验证当前文件状态**

Run: `python -c "from app.ingestion.sources import LocalSource; print('OK')"`
Expected: OK (if failing, the file is empty — proceed)

- [ ] **Step 2: 添加 WebSource 和 DBSource 导出**

```python
# app/ingestion/sources/__init__.py
from app.ingestion.sources.local import LocalSource
from app.ingestion.sources.web import WebSource
from app.ingestion.sources.database import DBSource

__all__ = ["LocalSource", "WebSource", "DBSource"]
```

- [ ] **Step 3: 验证导入**

```bash
python -c "from app.ingestion.sources import LocalSource, WebSource, DBSource; print('OK')"
```

Expected: OK

- [ ] **Step 4: Commit**

```bash
git add app/ingestion/sources/__init__.py
git commit -m "feat: export WebSource and DBSource from sources package"
```

---

### Task 9: Pipeline 三路 Fork 改造

**Files:**
- Modify: `app/ingestion/pipeline.py`
- Create: `tests/unit/ingestion/test_pipeline_fork.py`

- [ ] **Step 1: 写失败测试 — test_pipeline_fork.py**

```python
# tests/unit/ingestion/test_pipeline_fork.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.ingestion.pipeline import (
    run_semantic_path, run_graph_path, run_keyword_path,
    _compute_path_status,
)


@pytest.mark.asyncio
@patch("app.ingestion.pipeline.chunk_text")
@patch("app.ingestion.pipeline.embed_chunks")
@patch("app.ingestion.pipeline.write_chunks_to_milvus")
async def test_run_semantic_path(mock_write, mock_embed, mock_chunk):
    mock_chunk.return_value = [{"text": "chunk1", "metadata": {}}]
    mock_embed.return_value = [[0.1, 0.2]]
    mock_write.return_value = 1

    doc = MagicMock()
    doc.content = "test content"
    doc.id = "doc_001"
    doc.source_path = "/tmp/test.txt"

    count = await run_semantic_path(doc, "col_123", 1536)
    assert count == 1


@pytest.mark.asyncio
@patch("app.ingestion.pipeline.extract_candidate_entities")
@patch("app.ingestion.pipeline.extract_relations")
@patch("app.ingestion.pipeline.write_graph_to_neo4j")
@patch("app.ingestion.pipeline.get_kg_store")
async def test_run_graph_path(mock_kg, mock_write, mock_extract_rel, mock_extract_ent):
    mock_kg.return_value = AsyncMock()
    mock_extract_ent.return_value = [{"name": "Test", "score": 0.9, "type": "concept"}]
    mock_extract_rel.return_value = {
        "entities": [{"id": "e1", "name": "Test", "type": "concept", "aliases": []}],
        "relations": [],
    }
    mock_write.return_value = None

    doc = MagicMock()
    doc.content = "test content"
    doc.id = "doc_001"

    await run_graph_path(doc)
    mock_extract_ent.assert_called_once()
    mock_extract_rel.assert_called_once()
    mock_write.assert_called_once()


@pytest.mark.asyncio
@patch("app.ingestion.pipeline.write_document_to_es")
@patch("app.ingestion.pipeline.get_search_store")
async def test_run_keyword_path(mock_search, mock_write):
    mock_search.return_value = AsyncMock()
    mock_write.return_value = None

    doc = MagicMock()
    doc.id = "doc_001"
    doc.title = "Test Doc"
    doc.content = "Full content"
    doc.metadata_ = {"source_type": "local"}

    await run_keyword_path(doc, "col_123")
    mock_write.assert_called_once()


def test_compute_path_status_all_ok():
    results = [1, None, None]
    status = _compute_path_status(results)
    assert status == {"milvus": "ok", "neo4j": "ok", "es": "ok"}


def test_compute_path_status_neo4j_failed():
    results = [1, Exception("Neo4j down"), None]
    status = _compute_path_status(results)
    assert status == {"milvus": "ok", "neo4j": "error", "es": "ok"}


def test_compute_path_status_milvus_failed():
    results = [Exception("Milvus down"), None, None]
    status = _compute_path_status(results)
    assert status == {"milvus": "error", "neo4j": "ok", "es": "ok"}


def test_compute_path_status_all_failed():
    results = [Exception("a"), Exception("b"), Exception("c")]
    status = _compute_path_status(results)
    assert status == {"milvus": "error", "neo4j": "error", "es": "error"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/ingestion/test_pipeline_fork.py -v`
Expected: FAIL — `ImportError` (新函数尚未导出)

- [ ] **Step 3: 重构 pipeline.py**

将现有 `run_ingest_pipeline` 拆分为独立路径函数 + 三路平行 fork。完整实现：

```python
# app/ingestion/pipeline.py
import asyncio
import hashlib
from datetime import datetime, timezone
from app.adapters.vector_store.milvus import MilvusStore
from app.ingestion.sources.base import BaseSource
from app.ingestion.semantic_path.chunker import chunk_text
from app.ingestion.semantic_path.embedder import embed_chunks
from app.ingestion.semantic_path.milvus_writer import write_chunks_to_milvus
from app.domain.document import Document
from app.domain.ingest_job import IngestJob
from app.adapters.document_loader.pdf import PDFLoader
from app.adapters.document_loader.markdown import MarkdownLoader

LOADERS = {".pdf": PDFLoader, ".md": MarkdownLoader, ".txt": MarkdownLoader}


# === 三路路径函数 ===

async def run_semantic_path(doc, col_name: str, embedding_dim: int) -> int:
    """语义路径：分块 → Embedding → Milvus"""
    chunks = await chunk_text(doc.content, {"source": doc.source_path})
    if not chunks:
        raise ValueError("No chunks produced")
    embs = await embed_chunks(chunks)
    return await write_chunks_to_milvus(col_name, doc.id, chunks, embs)


async def run_graph_path(doc) -> None:
    """图谱路径：实体提取 → 关系提取 → Neo4j"""
    from app.ingestion.graph_path.entity_extractor import extract_candidate_entities
    from app.ingestion.graph_path.relation_extractor import extract_relations
    from app.ingestion.graph_path.neo4j_writer import write_graph_to_neo4j
    from app.core.di import get_kg_store

    candidates = await extract_candidate_entities(doc.content)
    if not candidates:
        return

    from app.adapters.llm.openai import OpenAILLM
    llm = OpenAILLM()
    result = await extract_relations(doc.content, candidates, llm)

    kg_store = await get_kg_store()
    await write_graph_to_neo4j(doc.id, result["entities"], result["relations"], kg_store)


async def run_keyword_path(doc, collection_id: str) -> None:
    """关键词路径：全文档 → ES"""
    from app.ingestion.keyword_path.es_writer import write_document_to_es
    from app.core.di import get_search_store

    search_store = await get_search_store()
    await write_document_to_es(
        doc.id, collection_id, doc.title, doc.content, doc.metadata_, search_store
    )


def _compute_path_status(results: list) -> dict:
    """将 asyncio.gather 的结果转为 path_status dict。

    results 顺序: [semantic_result, graph_result, keyword_result]
    """
    paths = ["milvus", "neo4j", "es"]
    return {
        path: "error" if isinstance(result, Exception) else "ok"
        for path, result in zip(paths, results)
    }


async def _handle_partial(doc_id: str, path_status: dict):
    """部分成功 → 入修复队列。"""
    from app.workers.repair import enqueue_repair

    FAILED_PATHS = ["neo4j", "es"]
    for path in FAILED_PATHS:
        if path_status.get(path) == "error":
            try:
                await enqueue_repair(doc_id, path, attempt=0)
            except Exception:
                pass


# === 主管道 ===

async def run_ingest_pipeline(
    job_id: str,
    collection_id: str,
    user_id: str,
    source: BaseSource,
    embedding_dim: int = 1536,
    db_session_factory=None,
):
    """统一摄入管道：Source → Parse → PG写入 → 三路并行 Fork → 状态汇总。"""
    files = await source.list_files()
    store = MilvusStore()
    col_name = f"col_{collection_id}"
    await store.create_collection(col_name, embedding_dim)
    total = len(files)
    completed, failed = 0, 0
    errors_list = []
    doc_id = None

    async with db_session_factory() as db:
        job = await db.get(IngestJob, job_id)
        if job:
            job.total_docs = total
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

    for fp in files:
        doc_id = None
        try:
            ext = f".{fp.rsplit('.', 1)[-1].lower()}" if "." in fp else ".txt"
            if ext == ".txt":
                ext = ".md"
            loader_cls = LOADERS.get(ext, MarkdownLoader)
            parsed = await loader_cls().load(fp)

            async with db_session_factory() as db:
                doc = Document(
                    collection_id=collection_id,
                    title=parsed.title,
                    source_type="local",
                    source_path=fp,
                    mime_type=parsed.mime_type,
                    file_size=parsed.file_size,
                    content_hash=hashlib.sha256(parsed.content.encode()).hexdigest(),
                    status="processing",
                )
                db.add(doc)
                await db.commit()
                await db.refresh(doc)
                doc_id = doc.id

            # 三路并行 Fork
            results = await asyncio.gather(
                run_semantic_path(doc, col_name, embedding_dim),
                run_graph_path(doc),
                run_keyword_path(doc, collection_id),
                return_exceptions=True,
            )

            path_status = _compute_path_status(results)

            if path_status["milvus"] == "ok":
                if all(v == "ok" for v in path_status.values()):
                    final_status = "ready"
                else:
                    final_status = "partial"
                    await _handle_partial(doc_id, path_status)
            else:
                final_status = "error"

            async with db_session_factory() as db:
                d = await db.get(Document, doc_id)
                if d:
                    d.status = final_status
                    d.path_status = path_status
                    if final_status != "error":
                        d.chunk_count = results[0] if isinstance(results[0], int) else 0
                        d.embedding_model = "text-embedding-3-small"
                        d.ingested_at = datetime.now(timezone.utc)
                    else:
                        d.error_message = str(results[0])
                    await db.commit()

            if final_status != "error":
                completed += 1
            else:
                failed += 1
                errors_list.append({"file": fp, "error": str(results[0]), "retryable": False})

        except Exception as e:
            failed += 1
            errors_list.append({"file": fp, "error": str(e), "retryable": True})
            async with db_session_factory() as db:
                if doc_id:
                    d = await db.get(Document, doc_id)
                    if d:
                        d.status = "error"
                        d.error_message = str(e)
                        await db.commit()

    async with db_session_factory() as db:
        job = await db.get(IngestJob, job_id)
        if job:
            job.completed_docs = completed
            job.failed_docs = failed
            job.errors = errors_list
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

    return {"completed": completed, "failed": failed}
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/unit/ingestion/test_pipeline_fork.py -v`
Expected: 7 tests PASS

- [ ] **Step 5: 运行已有测试确保不破坏**

Run: `pytest tests/ -x -v`
Expected: 已有 6 个 agent/adapter 测试仍然 PASS

- [ ] **Step 6: Commit**

```bash
git add app/ingestion/pipeline.py tests/unit/ingestion/test_pipeline_fork.py
git commit -m "feat: fork ingestion pipeline into 3 parallel paths with path_status"
```

---

### Task 10: Repair Worker (ARQ 指数退避)

**Files:**
- Create: `app/workers/repair.py`
- Create: `tests/unit/ingestion/test_repair.py`

- [ ] **Step 1: 写失败测试 — test_repair.py**

```python
# tests/unit/ingestion/test_repair.py
import pytest
from unittest.mock import AsyncMock, patch
from app.workers.repair import enqueue_repair, BACKOFF


def test_backoff_length():
    assert len(BACKOFF) == 4
    assert BACKOFF == [60, 300, 900, 3600]


@pytest.mark.asyncio
@patch("app.workers.repair.create_pool")
async def test_enqueue_repair(mock_create_pool):
    mock_redis = AsyncMock()
    mock_redis.enqueue_job.return_value = AsyncMock(job_id="repair_001")
    mock_create_pool.return_value = mock_redis

    await enqueue_repair("doc_001", "neo4j", attempt=0)

    mock_redis.enqueue_job.assert_called_once()
    call_args = mock_redis.enqueue_job.call_args
    assert call_args[0][0] == "repair_document_path"
    assert call_args[0][1] == "doc_001"
    assert call_args[0][2] == "neo4j"
    assert call_args[0][3] == 0


@pytest.mark.asyncio
@patch("app.workers.repair._repair_graph_path")
@patch("app.workers.repair._update_path_status")
@patch("app.workers.repair._check_all_ok_and_set_ready")
async def test_repair_document_path_neo4j_success(
    mock_check_ready, mock_update_status, mock_repair
):
    mock_repair.return_value = None
    mock_update_status.return_value = None
    mock_check_ready.return_value = None

    mock_ctx = {}

    from app.workers.repair import repair_document_path
    await repair_document_path(mock_ctx, "doc_001", "neo4j", attempt=0)

    mock_repair.assert_called_once_with("doc_001")
    mock_update_status.assert_called_once_with("doc_001", "neo4j", "ok")
    mock_check_ready.assert_called_once_with("doc_001")


@pytest.mark.asyncio
@patch("app.workers.repair._repair_graph_path")
async def test_repair_abandons_after_max_attempts(mock_repair):
    mock_repair.side_effect = Exception("still failing")
    mock_ctx = {"redis": AsyncMock()}

    from app.workers.repair import repair_document_path
    await repair_document_path(mock_ctx, "doc_001", "neo4j", attempt=3)

    mock_ctx["redis"].enqueue_job.assert_not_called()


@pytest.mark.asyncio
@patch("app.workers.repair._repair_graph_path")
async def test_repair_reenqueues_on_failure(mock_repair):
    mock_repair.side_effect = Exception("still failing")
    mock_redis = AsyncMock()
    mock_ctx = {"redis": mock_redis}

    from app.workers.repair import repair_document_path
    await repair_document_path(mock_ctx, "doc_001", "neo4j", attempt=1)

    mock_redis.enqueue_job.assert_called_once()
    call_args = mock_redis.enqueue_job.call_args
    assert call_args[0][0] == "repair_document_path"
    assert call_args[0][3] == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/ingestion/test_repair.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 repair.py**

```python
# app/workers/repair.py
import structlog
from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import get_settings
from app.core.di import async_session

logger = structlog.get_logger()
settings = get_settings()

BACKOFF = [60, 300, 900, 3600]


async def enqueue_repair(doc_id: str, failed_path: str, attempt: int = 0):
    """将修复任务入队 ARQ。"""
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job(
        "repair_document_path", doc_id, failed_path, attempt
    )


async def repair_document_path(ctx, doc_id: str, failed_path: str, attempt: int):
    """ARQ job: 修复单个文档的单个存储路径，指数退避重试。"""
    if attempt >= len(BACKOFF):
        logger.warning("repair abandoned", doc_id=doc_id, path=failed_path)
        return

    try:
        if failed_path == "neo4j":
            await _repair_graph_path(doc_id)
        elif failed_path == "es":
            await _repair_keyword_path(doc_id)

        await _update_path_status(doc_id, failed_path, "ok")
        await _check_all_ok_and_set_ready(doc_id)
        logger.info("repair succeeded", doc_id=doc_id, path=failed_path)

    except Exception as e:
        if attempt + 1 < len(BACKOFF):
            delay = BACKOFF[attempt]
            logger.warning(
                "repair failed, re-enqueuing",
                doc_id=doc_id, path=failed_path,
                attempt=attempt, next_delay=delay, error=str(e),
            )
            await ctx["redis"].enqueue_job(
                "repair_document_path", doc_id, failed_path, attempt + 1,
                _defer_by=delay,
            )
        else:
            logger.error(
                "repair abandoned after max attempts",
                doc_id=doc_id, path=failed_path, error=str(e),
            )


async def _repair_graph_path(doc_id: str):
    from app.ingestion.pipeline import run_graph_path
    doc = await _load_document(doc_id)
    await run_graph_path(doc)


async def _repair_keyword_path(doc_id: str):
    from app.ingestion.pipeline import run_keyword_path
    doc = await _load_document(doc_id)
    await run_keyword_path(doc, doc.collection_id)


async def _load_document(doc_id: str):
    from app.domain.document import Document

    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        if doc is None:
            raise ValueError(f"Document {doc_id} not found")
        return doc


async def _update_path_status(doc_id: str, path: str, status: str):
    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        if doc:
            current = doc.path_status or {}
            current[path] = status
            doc.path_status = current
            await db.commit()


async def _check_all_ok_and_set_ready(doc_id: str):
    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        if doc and doc.path_status:
            if all(v == "ok" for v in doc.path_status.values()):
                doc.status = "ready"
                await db.commit()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/ingestion/test_repair.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/workers/repair.py tests/unit/ingestion/test_repair.py
git commit -m "feat: add ARQ repair worker with exponential backoff"
```

---

### Task 11: Workers 集成 (main.py + ingest.py 更新)

**Files:**
- Modify: `app/workers/main.py`
- Modify: `app/workers/ingest.py`
- Modify: `app/api/v1/ingestion.py`

- [ ] **Step 1: 更新 workers/main.py — 注册 repair 函数**

```python
# app/workers/main.py
from arq.connections import RedisSettings
from app.core.config import get_settings
from app.workers.ingest import start_ingest_job
from app.workers.repair import repair_document_path

settings = get_settings()


class WorkerSettings:
    functions = [
        start_ingest_job,
        repair_document_path,
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 3600
```

- [ ] **Step 2: 更新 workers/ingest.py — 支持 web/db 来源**

```python
# app/workers/ingest.py
from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import get_settings
from app.core.di import async_session
from app.ingestion.pipeline import run_ingest_pipeline
from app.ingestion.sources.local import LocalSource
from app.ingestion.sources.web import WebSource
from app.ingestion.sources.database import DBSource

settings = get_settings()


async def start_ingest_job(
    ctx,
    job_id: str,
    collection_id: str,
    user_id: str,
    source_type: str,
    source_config: dict,
    embedding_dim: int = 1536,
):
    """ARQ job: 启动摄入管道。

    Args:
        source_type: "local" | "web" | "database"
        source_config:
            - local: {"file_paths": [...]}
            - web: {"urls": [...], "max_depth": 1}
            - database: {"db_url": "...", "query": "...",
                         "title_column": "...", "content_columns": [...]}
    """
    if source_type == "local":
        source = LocalSource(source_config["file_paths"])
    elif source_type == "web":
        source = WebSource(
            source_config["urls"],
            source_config.get("max_depth", 1),
        )
    elif source_type == "database":
        source = DBSource(
            source_config["db_url"],
            source_config["query"],
            source_config["title_column"],
            source_config["content_columns"],
        )
    else:
        raise ValueError(f"Unknown source_type: {source_type}")

    return await run_ingest_pipeline(
        job_id, collection_id, user_id, source, embedding_dim, async_session,
    )


async def enqueue_ingest(
    job_id: str,
    collection_id: str,
    user_id: str,
    source_type: str,
    source_config: dict,
):
    """将摄入任务入队 ARQ。"""
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    arq_job = await redis.enqueue_job(
        "start_ingest_job",
        job_id, collection_id, user_id, source_type, source_config,
    )
    return arq_job.job_id
```

- [ ] **Step 3: 更新 API 调用方 (ingestion.py)**

`app/api/v1/ingestion.py` 中的 `enqueue_ingest` 调用适配新签名：

```python
arq_job_id = await enqueue_ingest(
    str(job.id), collection_id, user.id,
    source_type="local",
    source_config={"file_paths": saved},
)
```

- [ ] **Step 4: 验证所有导入**

```bash
python -c "from app.workers.main import WorkerSettings; print('OK')"
python -c "from app.workers.ingest import start_ingest_job, enqueue_ingest; print('OK')"
```

Expected: 两次输出 "OK"

- [ ] **Step 5: 运行已有测试**

Run: `pytest tests/ -x -v`
Expected: 所有已有测试仍然通过

- [ ] **Step 6: Commit**

```bash
git add app/workers/main.py app/workers/ingest.py app/api/v1/ingestion.py
git commit -m "feat: update workers for SP2 - multi-source ingest + repair"
```

---

### Task 12: 集成测试 — 全部新模块导入

**Files:**
- Create: `tests/unit/ingestion/test_all_imports.py`

- [ ] **Step 1: 写汇总导入测试**

```python
# tests/unit/ingestion/test_all_imports.py


def test_import_entity_extractor():
    from app.ingestion.graph_path.entity_extractor import extract_candidate_entities
    assert extract_candidate_entities is not None


def test_import_relation_extractor():
    from app.ingestion.graph_path.relation_extractor import extract_relations, RELATION_SCHEMA
    assert extract_relations is not None
    assert RELATION_SCHEMA is not None


def test_import_neo4j_writer():
    from app.ingestion.graph_path.neo4j_writer import write_graph_to_neo4j
    assert write_graph_to_neo4j is not None


def test_import_es_writer():
    from app.ingestion.keyword_path.es_writer import write_document_to_es
    assert write_document_to_es is not None


def test_import_web_source():
    from app.ingestion.sources.web import WebSource
    assert WebSource is not None


def test_import_db_source():
    from app.ingestion.sources.database import DBSource
    assert DBSource is not None


def test_import_repair_worker():
    from app.workers.repair import repair_document_path, enqueue_repair, BACKOFF
    assert repair_document_path is not None
    assert enqueue_repair is not None
    assert BACKOFF is not None


def test_import_pipeline_functions():
    from app.ingestion.pipeline import (
        run_semantic_path, run_graph_path, run_keyword_path,
        _compute_path_status, run_ingest_pipeline,
    )
    assert run_semantic_path is not None
    assert run_graph_path is not None
    assert run_keyword_path is not None
    assert _compute_path_status is not None
    assert run_ingest_pipeline is not None
```

- [ ] **Step 2: 运行汇总导入测试**

Run: `pytest tests/unit/ingestion/test_all_imports.py -v`
Expected: 8 tests PASS

- [ ] **Step 3: 运行全部测试**

Run: `pytest tests/ -x -v`
Expected: 全部测试通过（约 35+ tests）

- [ ] **Step 4: Commit**

```bash
git add tests/unit/ingestion/test_all_imports.py
git commit -m "test: add import verification tests for all SP2 modules"
```

---

## 验证清单

完成后执行：

```bash
# 1. 全部测试
pytest tests/ -x -v

# 2. 全部模块导入
python -c "
from app.ingestion.graph_path.entity_extractor import extract_candidate_entities
from app.ingestion.graph_path.relation_extractor import extract_relations
from app.ingestion.graph_path.neo4j_writer import write_graph_to_neo4j
from app.ingestion.keyword_path.es_writer import write_document_to_es
from app.ingestion.sources.web import WebSource
from app.ingestion.sources.database import DBSource
from app.workers.repair import repair_document_path, enqueue_repair
from app.ingestion.pipeline import run_semantic_path, run_graph_path, run_keyword_path
print('ALL IMPORTS OK')
"

# 3. Workers 配置验证
python -c "from app.workers.main import WorkerSettings; print(len(WorkerSettings.functions))"
# Expected: 2 (start_ingest_job + repair_document_path)
```