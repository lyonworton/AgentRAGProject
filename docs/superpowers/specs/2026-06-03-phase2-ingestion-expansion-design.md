# Sub-project 2: 摄入扩展 — 设计文档

> 日期: 2026-06-03
> 状态: 已确认
> 父规格: docs/superpowers/specs/2026-06-03-phase2-infrastructure-design.md
> Phase: 2 (Week 5)

---

## 1. 概述

Sub-project 2 扩展摄入管道，从 Phase 1 的单路径（semantic_path → Milvus）升级为三路并行管道，并新增两种摄入源。

### 交付物

1. **graph_path**: jieba + TF-IDF 候选实体提取 → LLM 消歧 + 关系提取 → Neo4j 写入
2. **keyword_path**: 全文档 ES 写入（不分块）
3. **WebSource**: httpx + BeautifulSoup，URL 列表摄入
4. **DBSource**: SQLAlchemy 通用连接器，任意 SQL 数据库行→文档
5. **Repair Worker**: ARQ 指数退避修复队列
6. **Pipeline Fork**: 三路 asyncio.gather 并行 + path_status 汇总

---

## 2. 技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 实体提取 | jieba + TF-IDF (方案 C) | 中文友好、零安装成本、LLM 仅做消歧+关系提取降低成本 |
| Web 摄入 | httpx + BeautifulSoup (方案 B) | URL 列表 + 基础去噪，max_depth=1，力度适中 |
| DB 摄入 | SQLAlchemy 通用适配 (方案 C) | 自动识别方言，覆盖面最广，代码量最小 |
| 并行策略 | asyncio.gather(return_exceptions=True) | 单路径失败不阻塞其他路径 |
| 修复策略 | ARQ 指数退避 (60s→300s→900s→3600s) | 复用已有 ARQ 基础设施 |

---

## 3. 文件结构

```
新增 (9 files):
  app/ingestion/graph_path/__init__.py
  app/ingestion/graph_path/entity_extractor.py    # jieba + TF-IDF 候选实体
  app/ingestion/graph_path/relation_extractor.py   # LLM 关系提取 + 消歧
  app/ingestion/graph_path/neo4j_writer.py         # 写 Neo4j
  app/ingestion/keyword_path/__init__.py
  app/ingestion/keyword_path/es_writer.py          # 全文档写 ES
  app/ingestion/sources/web.py                     # httpx + BeautifulSoup
  app/ingestion/sources/database.py                # SQLAlchemy 通用连接器
  app/workers/repair.py                            # ARQ 修复 worker

修改 (5 files):
  app/ingestion/pipeline.py          # 三路并行 Fork + path_status 汇总
  app/ingestion/sources/__init__.py  # 导出 WebSource, DBSource
  app/workers/main.py                # 注册 repair 函数
  app/workers/ingest.py              # 扩展支持 web/db 入队
  pyproject.toml                     # jieba, beautifulsoup4
```

### 依赖新增

```toml
"jieba>=0.42.1",
"beautifulsoup4>=4.12.0",
```

---

## 4. graph_path — 实体提取 (`entity_extractor.py`)

### 流程

```
text → jieba.posseg.cut() 分词+词性标注
     → 过滤名词类词性 (n, nr, ns, nt, nz)
     → TF-IDF 加权 (Counter 词频 + 逆文档频率)
     → 去重排序 → Top-N 候选实体
```

### 接口

```python
async def extract_candidate_entities(text: str, top_k: int = 50) -> list[dict]:
    """返回: [{"name": str, "score": float, "type": str}, ...]"""
```

### 设计要点

- jieba 不依赖额外模型文件，零安装成本
- TF-IDF 过滤高频无意义词（"文档"、"页面"等）
- 返回词性标注，供 LLM 消歧时参考
- 词性映射: n→concept, nr→person, ns→location, nt→organization, nz→term

---

## 5. graph_path — 关系提取 (`relation_extractor.py`)

### 流程

```
候选实体列表 + 原文本(截断3000字) → LLM 一次调用
  ├── 实体消歧: 同名不同义拆分为不同实体，同义不同名合并
  └── 关系提取: 找出实体间的语义关系
```

### 接口

```python
async def extract_relations(
    text: str, entities: list[dict], llm: BaseLLM
) -> dict:
    """返回: {"entities": [...], "relations": [...]}"""
```

### LLM Prompt 设计

- 输入: 原文本(前3000字) + JSON 格式候选实体列表
- 输出: 结构化 JSON `{entities: [{id, name, type, aliases}], relations: [{from_entity, to_entity, type}]}`
- 关系类型: `RELATED_TO`, `PART_OF`, `DEPENDS_ON`, `PRODUCES`, `DESCRIBES`
- 使用 `BaseLLM.agenerate_structured()` 确保输出格式

### 设计要点

- LLM 同时做消歧 + 关系提取，一次调用减少延迟和成本
- 文本截断到 3000 字符，平衡上下文和 token 成本
- 复用已有的 `BaseLLM.agenerate_structured()` 接口

---

## 6. graph_path — Neo4j 写入器 (`neo4j_writer.py`)

### 接口

```python
async def write_graph_to_neo4j(
    doc_id: str, entities: list[dict], relations: list[dict],
) -> None:
    """通过 DI 获取 kg_store，调用 acreate_graph() 写入"""
```

### 设计要点

- 薄封装层，直接调用 `Neo4jKGStore.acreate_graph(doc_id, entities, relations)`
- 通过 DI 获取 store 实例，遵循 SP1 建立的模式
- 异常向上传播给 pipeline 的 gather

---

## 7. keyword_path — ES 写入器 (`es_writer.py`)

### 接口

```python
async def write_document_to_es(
    doc_id: str, collection_id: str, title: str,
    content: str, metadata: dict,
) -> None:
    """全文档写入 ES（不分块）"""
```

### 设计要点

- 写入完整文档内容，不是 chunk 级别
- 调用 `ElasticsearchStore.aindex_document()`
- metadata 包含: source_path, source_type, mime_type, language, page_number (如有)
- 原因: 倒排索引 + BM25 在小块上降低召回精度，文档级或大段(2000+词)写入才能保证精确匹配

---

## 8. WebSource (`sources/web.py`)

### 实现

```python
class WebSource(BaseSource):
    def __init__(self, urls: list[str], max_depth: int = 1):
        ...

    async def list_files(self) -> list[str]:
        # 对每个 URL 爬取 → 保存为临时文件 → 返回路径列表

    async def get_file_content(self, file_path: str) -> bytes:
        # 从临时文件读取内容

    async def _fetch_and_extract(self, url: str) -> str:
        # httpx GET → BeautifulSoup parse
        # 去除 script/style/nav/footer/header 标签
        # 返回纯文本
```

### 设计要点

- 继承 `BaseSource`，与 `LocalSource` 一致的模式
- httpx 复用已有依赖，BeautifulSoup 做正文提取
- 去噪: 移除 `script, style, nav, footer, header` 标签
- max_depth=1: 只爬取指定 URL，不跟踪链接
- 爬取后保存为临时 `.txt` 文件，复用现有 parser 链
- 超时 30s，异常向上传播让 pipeline 处理

---

## 9. DBSource (`sources/database.py`)

### 实现

```python
class DBSource(BaseSource):
    def __init__(
        self, db_url: str, query: str,
        title_column: str, content_columns: list[str]
    ):
        ...

    async def list_files(self) -> list[str]:
        # SQLAlchemy create_engine(db_url) → execute(query)
        # 每行 → 结构化文本 → 保存为临时文件 → 返回路径列表

    async def get_file_content(self, file_path: str) -> bytes:
        # 从临时文件读取内容

    def _row_to_document(self, row) -> str:
        # title_column → "# {title}"
        # content_columns → 拼接为正文段落
```

### 设计要点

- SQLAlchemy `create_engine(db_url)` 自动识别方言 (PG/MySQL/SQLite/MSSQL)
- 用户提供查询语句 + 字段映射，灵活适配任意表结构
- 行 → 文档格式: `# {title}\n\n{content_1}\n\n{content_2}...`
- 用同步 engine（DB source 是配置阶段一次性执行，不需要连接池）
- 保存为临时 `.md` 文件，复用 MarkdownParser

---

## 10. Pipeline 三路 Fork 改造 (`pipeline.py`)

### 新架构

```
Source → [Parse] → PG写入(status=processing) → Fork:
                                                    │
                                    ┌───────────────┼───────────────┐
                                    │               │               │
                              semantic_path    graph_path     keyword_path
                              (已有,稍改)       (新增)         (新增)
                                    │               │               │
                                    ▼               ▼               ▼
                                Milvus           Neo4j             ES
                                    │               │               │
                                    └───────────────┼───────────────┘
                                                    │
                                          asyncio.gather()
                                          (return_exceptions=True)
                                                    │
                                          ┌─────────┴─────────┐
                                          │ 汇总 path_status    │
                                          │ 判定 final status   │
                                          │ partial → repair   │
                                          └───────────────────┘
```

### 路径函数

```python
async def run_semantic_path(doc, col_name: str, embedding_dim: int):
    """已有逻辑，提取为独立函数"""
    chunks = await chunk_text(doc.content, {"source": doc.source_path})
    embs = await embed_chunks(chunks)
    return await write_chunks_to_milvus(col_name, doc.id, chunks, embs)

async def run_graph_path(doc):
    """新增: 实体提取 → 关系提取 → Neo4j 写入"""
    from app.ingestion.graph_path.entity_extractor import extract_candidate_entities
    from app.ingestion.graph_path.relation_extractor import extract_relations
    from app.ingestion.graph_path.neo4j_writer import write_graph_to_neo4j
    candidates = await extract_candidate_entities(doc.content)
    result = await extract_relations(doc.content, candidates)
    await write_graph_to_neo4j(doc.id, result["entities"], result["relations"])

async def run_keyword_path(doc, collection_id: str):
    """新增: 全文档 ES 写入"""
    from app.ingestion.keyword_path.es_writer import write_document_to_es
    await write_document_to_es(
        doc.id, collection_id, doc.title, doc.content, doc.metadata_
    )
```

### 状态判定

| path_status | final status | 动作 |
|-------------|-------------|------|
| 三路全 ok | `ready` | 无 |
| milvus ok, 其他部分失败 | `partial` | 入修复队列 |
| milvus 失败 | `error` | 记录错误 |

### 修复入队

```python
FAILED_PATHS = ["neo4j", "es"]  # 仅非核心路径可延迟修复

async def _handle_partial(doc_id: str, path_status: dict):
    failed = [p for p in FAILED_PATHS if path_status.get(p) != "ok"]
    for path in failed:
        await enqueue_repair(doc_id, path, attempt=0)
```

---

## 11. Repair Worker (`workers/repair.py`)

### 指数退避

| attempt | delay | 说明 |
|---------|-------|------|
| 0 | 60s | 瞬时故障快速重试 |
| 1 | 300s (5min) | 服务短暂不可用 |
| 2 | 900s (15min) | 服务恢复中 |
| 3 | 3600s (1h) | 最终尝试，失败则放弃 |

### 接口

```python
BACKOFF = [60, 300, 900, 3600]

async def repair_document_path(ctx, doc_id: str, failed_path: str, attempt: int):
    """ARQ job: 修复单个文档的单个存储路径"""
    if attempt >= len(BACKOFF):
        return  # 放弃

    try:
        if failed_path == "neo4j":
            await _repair_graph_path(doc_id)
        elif failed_path == "es":
            await _repair_keyword_path(doc_id)
        await _update_path_status(doc_id, failed_path, "ok")
        await _check_all_ok_and_set_ready(doc_id)
    except Exception as e:
        if attempt + 1 < len(BACKOFF):
            await ctx["redis"].enqueue_job(
                "repair_document_path", doc_id, failed_path, attempt + 1,
                _defer_by=BACKOFF[attempt],
            )
```

### 设计要点

- 复用 ARQ 基础设施（`WorkerSettings` 注册）
- 指数退避通过 ARQ 的 `_defer_by` 实现延迟入队
- 放弃后文档保持 partial 状态，可通过 API 手动触发
- 修复逻辑与原始写入逻辑共用同一函数

---

## 12. Workers 集成

### `workers/main.py` 变更

```python
from app.workers.repair import repair_document_path

class WorkerSettings:
    functions = [
        start_ingest_job,
        repair_document_path,  # 新增
    ]
    # ... 其余不变
```

### `workers/ingest.py` 变更

```python
async def start_ingest_job(ctx, job_id, collection_id, user_id,
    source_type: str, source_config: dict, embedding_dim: int = 1536):
    """扩展: 支持 source_type="web"|"database"|"local" """
    if source_type == "local":
        source = LocalSource(source_config["file_paths"])
    elif source_type == "web":
        source = WebSource(source_config["urls"], source_config.get("max_depth", 1))
    elif source_type == "database":
        source = DBSource(
            source_config["db_url"], source_config["query"],
            source_config["title_column"], source_config["content_columns"],
        )
    return await run_ingest_pipeline(...)
```

---

## 13. API 扩展

### 新增端点

```
POST /api/v1/ingest/web        {"urls": [...], "collection_id": "...", "max_depth": 1}
POST /api/v1/ingest/database   {"db_url": "...", "query": "...", "title_column": "...",
                                "content_columns": [...], "collection_id": "..."}
GET  /api/v1/collections/{id}/repair-status   → {partial: N, error: N, docs: [...]}
POST /api/v1/collections/{id}/repair-all      → {enqueued: N}
```

### 已有端点 (不变)

```
POST /api/v1/ingest/local      → 已有
GET  /api/v1/ingest/{job_id}   → 已有
```

---

## 14. 验证标准

1. `python -c "import jieba; list(jieba.cut('测试分词')); print('OK')"` → jieba 安装成功
2. `python -c "from bs4 import BeautifulSoup; print('OK')"` → beautifulsoup4 安装成功
3. `python -c "from app.ingestion.graph_path.entity_extractor import extract_candidate_entities; print('OK')"` → 导入成功
4. `python -c "from app.ingestion.graph_path.relation_extractor import extract_relations; print('OK')"` → 导入成功
5. `python -c "from app.ingestion.graph_path.neo4j_writer import write_graph_to_neo4j; print('OK')"` → 导入成功
6. `python -c "from app.ingestion.keyword_path.es_writer import write_document_to_es; print('OK')"` → 导入成功
7. `python -c "from app.ingestion.sources.web import WebSource; print('OK')"` → 导入成功
8. `python -c "from app.ingestion.sources.database import DBSource; print('OK')"` → 导入成功
9. `python -c "from app.workers.repair import repair_document_path; print('OK')"` → 导入成功
10. `pytest tests/ -x -v` → 已有 6 个测试仍然通过
11. Pipeline 三路并行逻辑在单元测试中验证（mock 三路）
12. WebSource + DBSource 在单元测试中验证（mock httpx/SQLAlchemy）

---

## 15. 不在此范围

- JS 渲染的 web 爬取（Playwright）
- 整站递归爬取（max_depth > 1 的链接跟踪）
- 数据库增量同步 (CDC)
- 图路径的语义搜索增强（当前用 CONTAINS 简单匹配）