# Phase 5: 补完原始设计 — 设计文档

> 日期: 2026-06-07
> 状态: 已确认
> 项目: AgentRAGProject
> 基于: docs/superpowers/specs/2026-06-02-adaptive-agent-rag-design.md §10 Phase 2

---

## 1. 概述

### 1.1 目标

补完原始设计文档中 Phase 2 规划但被推迟的内容：

1. **Neo4j 知识图谱** — 代码已完整实现（adapter + entity/relation提取 + 写入 + KG搜索），docker-compose 已定义，仅需启动验证
2. **Elasticsearch 全文检索** — 代码已完整实现（adapter + IK分词 + 写入 + keyword搜索），docker-compose 已定义，仅需启动验证
3. **可插拔重排序** — RRF(默认) + BGE-reranker-v2-m3 + Cohere Rerank，替代当前 score-sort+dedup
4. **集成测试** — 真实容器端到端验证三路检索链路

### 1.2 不变的部分

| 组件 | 现状 | 说明 |
|------|------|------|
| Router 意图路由 | ✅ 已是真实 LLM 路由 | 无需改动 |
| DBSource 数据库摄入 | ✅ 已实现（sync） | ARQ worker 后台执行，不需改 |
| Ingestion 三路 fork | ✅ `asyncio.gather` 并行 | 无需改动 |
| Executor 并行检索 | ✅ `asyncio.gather` 并行 | 仅改排重部分 |
| Startup events | ✅ 已有 Neo4j/ES pre-warm（warn-only） | 无需改动 |
| DI singletons | ✅ 已有 kg_store/search_store | 无需改动 |

---

## 2. Docker Compose 变更

### 2.1 现有状态

Neo4j 和 ES 在 docker-compose.yml 第 60-79 行**已完整定义**（包括 ES 使用 Dockerfile.es IK 分词镜像），只是服务从未启动过。Phase 5 需要做的是修正配置，不是从头添加。

### 2.2 修正内容

**Neo4j — 加 healthcheck interval/timeout/retries**：

当前 neo4j 的 healthcheck 没有 interval/timeout/retries 参数，Docker 用默认值（interval 30s，retries 3），首次启动可能超时。改为：

```yaml
neo4j:
  image: neo4j:5
  ports: ["7474:7474", "7687:7687"]
  environment:
    NEO4J_AUTH: neo4j/${NEO4J_PASSWORD:-agentrag123}
  volumes: [neo4jdata:/data]
  healthcheck:
    test: ["CMD-SHELL", "echo 'RETURN 1' | cypher-shell -u neo4j -p $${NEO4J_PASSWORD:-agentrag123} || exit 1"]
    interval: 10s
    timeout: 10s
    retries: 10           # Neo4j 首次启动 ~60s
    start_period: 30s     # 给初始引导留时间
```

**Elasticsearch — 加 healthcheck + 降内存**：

当前没有 healthcheck，内存 1GB 对开发环境浪费。`Dockerfile.es` 基于 `elasticsearch:8.12.0`，是 RHEL UBI 镜像，没有 `curl`，用 ES 内置 Java HTTP 检测：

```yaml
elasticsearch:
  build:
    context: .
    dockerfile: Dockerfile.es
  ports: ["9200:9200"]
  environment:
    discovery.type: single-node
    xpack.security.enabled: false
    ES_JAVA_OPTS: -Xms512m -Xmx512m    # 1g → 512m
  volumes: [esdata:/usr/share/elasticsearch/data]
  healthcheck:
    test: ["CMD-SHELL", "curl -sf http://localhost:9200/_cluster/health | grep -q 'green\|yellow' || exit 1"]
    interval: 10s
    timeout: 10s
    retries: 10
    start_period: 30s
```

**fastapi / arq-worker — depends_on 加 condition: service_healthy**：

```yaml
fastapi:
  depends_on:
    postgres:
      condition: service_started
    milvus:
      condition: service_started
    redis:
      condition: service_started
    neo4j:
      condition: service_healthy       # 新增
    elasticsearch:
      condition: service_healthy       # 新增

arq-worker:
  depends_on:
    postgres:
      condition: service_started
    milvus:
      condition: service_started
    redis:
      condition: service_started
    neo4j:
      condition: service_healthy       # 新增 — ingestion 需要写 Neo4j
    elasticsearch:
      condition: service_healthy       # 新增 — ingestion 需要写 ES
```

**fastapi — 内存限制**（BGE 模型需要）：

```yaml
fastapi:
  mem_limit: 3g            # BGE-reranker-v2-m3 ~1.5GB FP16 + 应用
```

### 2.3 配置对齐

`.env` 中的 Neo4j/ES 地址是 `localhost`，Docker 容器内 `docker-compose` 已通过 `environment` 覆盖（`NEO4J_URI=bolt://neo4j:7687`, `ES_HOST=http://elasticsearch:9200`）。需要在 `app/core/config.py` 新增 reranker 字段（见 §3），`docker-compose.yml` 的 `environment` 中也加对应的 override。

### 2.4 关键决策

| 决策 | 理由 |
|------|------|
| ES 512MB heap | 开发环境够用，IK 分词不需要大内存 |
| ES 关闭安全认证 | 仅绑 Docker 内网，外网不可达 |
| fastapi mem_limit 3GB | BGE 模型 ~1.5GB + Python 进程 |
| depends_on service_healthy | 确保 Neo4j/ES 完全就绪后才启动 API |
| arq-worker 也依赖 Neo4j/ES | ingestion 需要写入三路 |

---

## 3. Reranker 可插拔架构

### 3.1 两阶段排序流程

```
三路检索结果（每路有自己的排名 + 原始分数）
     │
     ▼
┌────────────────┐
│ 阶段1: RRF 融合 │  ← 永远执行，零成本
│ 按 source 分组    │     Milvus cosine / ES BM25 / KG 固定值
│ 组内排名 → RRF   │     三者不可比较 → RRF 只看排名
└───────┬────────┘
        │
        ▼
   provider=rrf? ───yes──→ chunk_id 去重 → 按 RRF 分降序 → 输出
        │
        no (bge/cohere)
        │
        ▼
┌────────────────┐
│ 阶段2: 语义精排  │  ← 仅对 RRF top_k 候选执行
│ BGE 或 Cohere    │     大幅减少计算量
└───────┬────────┘
        │
        ▼
  chunk_id 去重 → 按精排分降序 → 输出
```

**核心设计理由**：
- 当前 executor_node (executor.py:99) 用 `all_hits.sort(key=lambda h: h["score"], reverse=True)` — 但 Milvus 返回 cosine 分数 (~0.85)、ES 返回 BM25 分数 (可能是 8.5)、KG 返回固定 0.5，三者直接比大小毫无意义
- RRF 只看排名不看绝对值，天然跨源可比，专为多路检索融合设计
- 用 `_tool` tag 区分每路来源，组内按原始分数排名，组间用 RRF 融合

### 3.2 文件结构

```
app/adapters/reranker/
├── __init__.py          # 导出符号
├── base.py              # BaseReranker 抽象接口 + TwoStageReranker 组合器
├── rrf.py               # Reciprocal Rank Fusion
├── bge.py               # BGE-reranker-v2-m3 (FlagEmbedding)
├── cohere.py            # Cohere Rerank API
└── factory.py           # get_reranker() 工厂函数
```

### 3.3 接口定义

```python
# app/adapters/reranker/base.py
from abc import ABC, abstractmethod

class BaseReranker(ABC):
    """重排序器抽象。documents 已包含 _tool source tag 和 source 内排名。"""
    @abstractmethod
    async def rerank(
        self, query: str, documents: list[dict], top_k: int = 10
    ) -> list[dict]:
        """
        documents: [{"chunk_id": str, "text": str, "score": float,
                      "source": str, "_tool": str, ...}, ...]
        返回: 重排序后的 documents，附带新字段 _rerank_score
        """
        ...


class TwoStageReranker(BaseReranker):
    """组合两个 reranker：stage1 粗排 → top_k 截断 → stage2 精排"""
    def __init__(self, stage1: BaseReranker, stage2: BaseReranker, top_k: int):
        self._s1 = stage1
        self._s2 = stage2
        self._top_k = top_k

    async def rerank(self, query: str, documents: list[dict], top_k: int = 10) -> list[dict]:
        candidates = await self._s1.rerank(query, documents, self._top_k)
        return await self._s2.rerank(query, candidates, top_k)
```

### 3.4 RRF 实现

```python
# app/adapters/reranker/rrf.py
class RRFReranker(BaseReranker):
    """Reciprocal Rank Fusion: RRF_score(doc) = Σ 1/(k + rank_in_source(doc))"""
    def __init__(self, k: int = 60):
        self.k = k

    async def rerank(self, query: str, documents: list[dict], top_k: int = 10) -> list[dict]:
        # 1. 按 _tool 分组
        groups: dict[str, list[dict]] = {}
        for doc in documents:
            tool = doc.get("_tool", "unknown")
            groups.setdefault(tool, []).append(doc)

        # 2. 每组内按原始分数降序排名（下标 + 1 = rank）
        for tool, docs in groups.items():
            docs.sort(key=lambda d: d.get("score", 0), reverse=True)

        # 3. 计算 RRF 分数
        for doc in documents:
            doc["_rrf_score"] = 0.0
        for tool, docs in groups.items():
            for rank_idx, doc in enumerate(docs):
                doc["_rrf_score"] += 1.0 / (self.k + rank_idx + 1)

        # 4. 按 RRF 分降序，取 top_k
        documents.sort(key=lambda d: d.get("_rrf_score", 0), reverse=True)
        return documents[:top_k]
```

### 3.5 BGE 实现

```python
# app/adapters/reranker/bge.py
import asyncio

class BGEReranker(BaseReranker):
    """BGE-reranker-v2-m3 语义精排。FlagReranker 是同步的，用 asyncio.to_thread 包装。"""
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3", use_fp16: bool = True):
        from FlagEmbedding import FlagReranker
        self._model = FlagReranker(model_name, use_fp16=use_fp16)

    async def rerank(self, query: str, documents: list[dict], top_k: int = 10) -> list[dict]:
        if not documents:
            return []
        pairs = [[query, doc["text"]] for doc in documents]
        scores = await asyncio.to_thread(self._model.compute_score, pairs)
        if isinstance(scores, float):       # 单个 doc 时返回标量
            scores = [scores]
        for doc, score in zip(documents, scores):
            doc["_rerank_score"] = float(score)
        documents.sort(key=lambda d: d.get("_rerank_score", 0), reverse=True)
        return documents[:top_k]
```

### 3.6 Cohere 实现

```python
# app/adapters/reranker/cohere.py
import asyncio

class CohereReranker(BaseReranker):
    def __init__(self, api_key: str, model: str = "rerank-english-v3.0"):
        import cohere
        self._client = cohere.Client(api_key)
        self._model = model

    async def rerank(self, query: str, documents: list[dict], top_k: int = 10) -> list[dict]:
        if not documents:
            return []
        response = await asyncio.to_thread(
            self._client.rerank,
            query=query,
            documents=[d["text"] for d in documents],
            model=self._model,
            top_n=top_k,
        )
        # response.results: [{index: int, relevance_score: float}, ...]
        for r in response.results:
            documents[r.index]["_rerank_score"] = r.relevance_score
        documents.sort(key=lambda d: d.get("_rerank_score", 0), reverse=True)
        return documents[:top_k]
```

### 3.7 Factory

```python
# app/adapters/reranker/factory.py
from functools import lru_cache
from app.core.config import get_settings
from app.adapters.reranker.base import BaseReranker, TwoStageReranker
from app.adapters.reranker.rrf import RRFReranker
from app.adapters.reranker.bge import BGEReranker
from app.adapters.reranker.cohere import CohereReranker

@lru_cache()
def get_reranker() -> BaseReranker:
    s = get_settings()
    provider = s.reranker_provider

    # 阶段1: RRF 始终创建
    stage1 = RRFReranker(k=s.rrf_k)

    if provider == "rrf":
        return stage1

    if provider == "bge":
        stage2 = BGEReranker(model_name=s.reranker_model)
        return TwoStageReranker(stage1, stage2, top_k=s.reranker_top_k)

    if provider == "cohere":
        stage2 = CohereReranker(api_key=s.cohere_api_key or "")
        return TwoStageReranker(stage1, stage2, top_k=s.reranker_top_k)

    # 兜底
    import structlog
    structlog.get_logger().warning("unknown reranker provider, falling back to RRF",
                                   provider=provider)
    return stage1
```

### 3.8 配置字段

```python
# app/core/config.py 新增
reranker_provider: str = "rrf"                 # rrf | bge | cohere
reranker_model: str = "BAAI/bge-reranker-v2-m3"
reranker_top_k: int = 20                       # RRF 粗排后取前 N 条送精排
rrf_k: int = 60                                # RRF 公式参数
cohere_api_key: str = ""
```

```bash
# .env / .env.example 新增
RERANKER_PROVIDER=rrf
# RERANKER_MODEL=BAAI/bge-reranker-v2-m3
# RERANKER_TOP_K=20
# RRF_K=60
# COHERE_API_KEY=
```

docker-compose.yml fastapi/arq-worker `environment` 中无需新增 — 这些字段有合理默认值。

---

## 4. Executor 集成

### 4.1 当前流程（executor.py:86-116）

```
_execute_task() × N (asyncio.gather 并行)
    → 每个 task 调用 router 指定的 tools
    → 返回带 _tool 标签的结果

executor_node():
    all_hits = [] 合并所有结果
    all_hits.sort(key=score, reverse=True)   ← 问题: 跨源分数不可比
    chunk_id 去重 (保留最高分)
    → 输出 RetrievedChunk[]
```

### 4.2 新流程

```
_execute_task() × N (asyncio.gather 并行)     ← 不变
    → 每个 task 调用 router 指定的 tools
    → 返回带 _tool 标签的结果

executor_node():
    all_hits = [] 合并所有结果
    if all_hits:
        reranker = get_reranker()                     ← 新增
        all_hits = await reranker.rerank(             ← 新增: 两阶段重排
            state["query"], all_hits, top_k=10
        )
    chunk_id 去重 (保留 reranker 给的高分)             ← 微调: 排序字段改为 _rerank_score
    → 输出 RetrievedChunk[]
```

### 4.3 具体改动

executor.py 第 97-110 行（当前 score-sort + dedup）替换为：

```python
    # Rerank: replace naive score-sort with pluggable reranker
    if all_hits:
        from app.adapters.reranker.factory import get_reranker
        reranker = get_reranker()
        all_hits = await reranker.rerank(state["query"], all_hits, top_k=10)
    else:
        all_hits = []

    retrieved: list[RetrievedChunk] = []
    seen: set[str] = set()
    for hit in all_hits:
        if hit["chunk_id"] not in seen:
            retrieved.append(RetrievedChunk(
                chunk_id=hit["chunk_id"],
                document_id=hit.get("document_id", ""),
                text=hit["text"],
                score=hit.get("_rerank_score", hit["score"]),
                source=hit["source"],
                metadata={},
            ))
            seen.add(hit["chunk_id"])
```

**改动量**：仅 executor_node 函数中 ~15 行，不改变 executor.py 其他逻辑（`_execute_task`、`_resolve_groups` 完全不变）。

---

## 5. Health Check 扩容

health 端点在 `app/main.py:21-61`。当前检查 PG + Redis + Milvus。新增 Neo4j + ES：

```python
    # Neo4j — Phase 5
    try:
        from app.core.di import get_kg_store
        kg = await get_kg_store()
        await kg.ahealth_check()        # 待新增: Neo4jKGStore 加 ahealth_check 方法(跑 RETURN 1)
        checks["neo4j"] = "ok"
    except Exception as e:
        checks["neo4j"] = f"error: {e}"
        status["status"] = "degraded"   # degrade, NOT unhealthy — KG 路径降级即可

    # Elasticsearch — Phase 5
    try:
        from app.core.di import get_search_store
        es = await get_search_store()
        await es.ahealth_check()        # 待新增: ElasticsearchStore 加 ahealth_check 方法(跑 _cluster/health)
        checks["elasticsearch"] = "ok"
    except Exception as e:
        checks["elasticsearch"] = f"error: {e}"
        status["status"] = "degraded"
```

Neo4jKGStore 新增 `ahealth_check`：
```python
async def ahealth_check(self):
    await self._driver.execute_query("RETURN 1")
```

ElasticsearchStore 新增 `ahealth_check`：
```python
async def ahealth_check(self):
    await self._client.cluster.health()
```

---

## 6. 空 `__init__.py` 修正

- `app/ingestion/graph_path/__init__.py` (0 bytes) — 加导出: `EntityExtractor`, `RelationExtractor`, `Neo4jWriter`
- `app/ingestion/keyword_path/__init__.py` (0 bytes) — 加导出: `ESWriter`

---

## 7. 测试计划

### 7.1 单元测试（无需真实服务）

```
tests/unit/adapters/reranker/
├── __init__.py
├── test_rrf.py              # RRF 公式: 单源、多源、k参数、空输入
├── test_two_stage.py        # TwoStageReranker: stage1→截断→stage2 流向正确
├── test_bge.py              # BGE mock: 验证调用参数正确传递
├── test_cohere.py           # Cohere mock: 验证调用参数正确传递
└── test_factory.py          # rrf→RRFReranker, bge→TwoStageReranker, cohere→TwoStageReranker

tests/unit/agents/
└── test_executor_rerank.py  # executor_node 使用 mock reranker，验证 _rerank_score 流到 RetrievedChunk.score
```

### 7.2 集成测试（需要真实 Neo4j/ES）

```
tests/integration/
├── conftest.py                     # pytest_configure: 注册 "integration" marker
│                                   # fixtures: skip_if_no_neo4j, skip_if_no_es
├── test_neo4j_end_to_end.py        # entity 创建→relation 关联→KGSearchTool 搜索命中
├── test_elasticsearch_end_to_end.py  # doc 写入→KeywordSearchTool 搜索→IK 分词验证
├── test_three_way_retrieval.py     # 三路并行检索→RRF 融合→验证跨源排名正确
└── test_reranker.py                # BGE 真实模型下载→重排序验证（skipif no torch）
```

conftest.py 核心逻辑：
```python
import pytest
import os

def pytest_configure(config):
    config.addin_value("markers", "integration: tests requiring real Neo4j/ES/Milvus")

@pytest.fixture
def require_neo4j():
    host = os.environ.get("NEO4J_HOST", "localhost")
    try:
        from neo4j import GraphDatabase
        with GraphDatabase.driver(f"bolt://{host}:7687", auth=("neo4j", "agentrag123")) as d:
            d.verify_connectivity()
    except Exception:
        pytest.skip("Neo4j not available")

@pytest.fixture
def require_es():
    host = os.environ.get("ES_HOST", "http://localhost:9200")
    try:
        import httpx
        r = httpx.get(f"{host}/_cluster/health", timeout=5)
        if r.status_code != 200:
            pytest.skip("ES not available")
    except Exception:
        pytest.skip("ES not available")
```

### 7.3 运行方式

```bash
# 启动全量服务
docker compose up -d
# 等待 healthy
docker compose ps

# 单元测试（随时可跑）
pytest tests/unit/ -q

# 集成测试（需要全量服务 running）
pytest tests/integration/ -m integration -v

# 全部
pytest tests/ -q
```

---

## 8. 依赖变更

```toml
# pyproject.toml 新增（都是可选）
"FlagEmbedding>=1.2.0",    # BGE reranker，仅在 provider=bge 时需要
"cohere>=5.0.0",           # Cohere rerank，仅在 provider=cohere 时需要
```

默认 `provider=rrf` 零额外依赖。

---

## 9. 实现顺序

| SP | 内容 | 新增文件 | 修改文件 | 验证 |
|----|------|---------|---------|------|
| SP0 | Docker 修正 + config + health + `__init__.py` + ahealth_check | 0 | ~7 | `docker compose ps` 全 healthy，`GET /admin/health` 5/5 ok |
| SP1 | Reranker 架构（base/Twostage/rrf/bge/cohere/factory） | 6 | config.py | 5 个单元测试通过 |
| SP2 | Executor 集成两阶段重排序 | 0 | executor.py (~15行) | test_executor_rerank.py 通过 |
| SP3 | 集成测试 | 5 | 0 | `pytest tests/integration/ -m integration` 全部 pass |

---

## 10. 降级策略

| 场景 | 行为 | 实现方式 |
|------|------|---------|
| Neo4j 不可用 | KG 路径静默跳过，Milvus+ES 继续，health `degraded` | 已有：events.py warn-only + pipeline.py return_exceptions |
| ES 不可用 | Keyword 路径静默跳过，Milvus+KG 继续，health `degraded` | 同上 |
| BGE 模型下载失败 | 回退到纯 RRF 结果，日志 warning | factory.py try/except + 自动 fallback |
| Cohere API 超时/无 key | 回退到 RRF 结果，日志 warning | CohereReranker 内 catch + fallback 到 stage1 |
| Stage2 抛异常 | 返回 stage1 的 RRF 结果 | TwoStageReranker try/except |
| 全部检索不可用 | 降级到 memory-only 模式 | 已有 |

---

## 11. 文件变更总览

### 新增 (11 文件)
```
app/adapters/reranker/__init__.py
app/adapters/reranker/base.py
app/adapters/reranker/rrf.py
app/adapters/reranker/bge.py
app/adapters/reranker/cohere.py
app/adapters/reranker/factory.py
tests/unit/adapters/reranker/__init__.py
tests/unit/adapters/reranker/test_rrf.py
tests/unit/adapters/reranker/test_two_stage.py
tests/unit/adapters/reranker/test_bge.py
tests/unit/adapters/reranker/test_cohere.py
tests/unit/adapters/reranker/test_factory.py
tests/unit/agents/test_executor_rerank.py
tests/integration/__init__.py
tests/integration/conftest.py
tests/integration/test_neo4j_end_to_end.py
tests/integration/test_elasticsearch_end_to_end.py
tests/integration/test_three_way_retrieval.py
tests/integration/test_reranker.py
```

### 修改 (~8 文件)
```
docker-compose.yml           # healthcheck 参数 + depends_on condition + mem_limit
app/core/config.py           # 5 个 reranker 配置字段
app/main.py                  # health endpoint 加 Neo4j + ES
app/agents/executor.py       # ~15 行: score-sort → get_reranker.rerank
app/adapters/kg/neo4j.py     # +ahealth_check()
app/adapters/search/elasticsearch.py  # +ahealth_check()
app/ingestion/graph_path/__init__.py  # 加导出
app/ingestion/keyword_path/__init__.py  # 加导出
.env.example                 # 加 reranker 配置（注释掉的）
pyproject.toml               # 加 FlagEmbedding + cohere 可选依赖
```

---

## 12. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| BGE 模型 1.5GB 下载慢/失败 | provider=bge 无法使用 | 默认 rrf，BGE 可选；factory 自动 fallback |
| ES Dockerfile.es IK 插件下载失败 | ES 无中文分词 | IK URL 来自 GitHub，需网络；离线用预构建镜像 |
| Neo4j 首次启动 >60s 触发 timeout | fastapi 启动失败 | retries=10 + start_period=30s |
| Docker Desktop Windows 无 GPU | BGE CPU 推理慢 | top_k=20 默认，CPU 推理 ~200ms 可接受 |
| Milvus 也依赖 etcd+minio | 全量服务需要 8 个容器 | 开发机 16GB RAM 足够 |
| `asyncio.to_thread` + FlagReranker 阻塞 event loop | 查询延迟增加 | BGE 只对 top_k 候选打分，pool 大小可控 |

[[project-overview]] [[phase4-status]] [[key-arch-decisions]] [[known-issues]]