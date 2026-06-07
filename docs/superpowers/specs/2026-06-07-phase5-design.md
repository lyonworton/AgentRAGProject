# Phase 5: 补完原始设计 — 设计文档

> 日期: 2026-06-07
> 状态: 已确认
> 项目: AgentRAGProject
> 基于: docs/superpowers/specs/2026-06-02-adaptive-agent-rag-design.md §10 Phase 2

---

## 1. 概述

### 1.1 目标

补完原始设计文档中 Phase 2 规划但被推迟的内容：

1. **Neo4j 知识图谱** — 代码已完整实现，仅需部署验证
2. **Elasticsearch 全文检索** — 代码已完整实现，仅需部署验证
3. **可插拔重排序** — RRF(默认) + BGE-reranker-v2-m3 + Cohere Rerank，替代当前 score-sort+dedup
4. **集成测试** — 真实容器端到端验证三路检索链路

### 1.2 不变的部分

| 组件 | 现状 | 说明 |
|------|------|------|
| Router 意图路由 | ✅ 已是真实 LLM 路由 | 无需改动 |
| DBSource 数据库摄入 | ✅ 已实现，保持 sync | ARQ worker 异步执行，不需要改 |
| Ingestion 三路 fork | ✅ `asyncio.gather` 并行 | 无需改动 |
| Executor 并行检索 | ✅ `asyncio.gather` 并行 | 仅改排重部分 |

---

## 2. Docker Compose 变更

### 2.1 取消注释的服务

```yaml
# === Phase 2 (Phase 5 启用) ===

neo4j:
  image: neo4j:5
  environment:
    - NEO4J_AUTH=neo4j/password
  ports:
    - "7474:7474"
    - "7687:7687"
  volumes:
    - neo4jdata:/data
  healthcheck:
    test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "password", "RETURN 1"]
    interval: 10s
    timeout: 10s
    retries: 5

elasticsearch:
  build:
    context: .
    dockerfile: Dockerfile.es
  environment:
    - discovery.type=single-node
    - xpack.security.enabled=false
    - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
  ports:
    - "9200:9200"
  volumes:
    - esdata:/data
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9200/_cluster/health"]
    interval: 10s
    timeout: 10s
    retries: 5
```

### 2.2 fastapi 容器资源调整

```yaml
fastapi:
  # ...
  mem_limit: 3g          # BGE-reranker-v2-m3 需要 ~1.5GB FP16
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_started
    neo4j:
      condition: service_healthy
    elasticsearch:
      condition: service_healthy
```

### 2.3 关键决策

| 决策 | 理由 |
|------|------|
| ES 关闭安全认证 | 开发环境，仅绑 localhost:9200 |
| ES 内存限制 512MB | 开发环境够用，节省资源 |
| fastapi 内存 3GB | BGE 模型 ~1.5GB + 应用本身 |
| healthcheck 条件启动 | 确保 Neo4j/ES 就绪后才启动 API |

---

## 3. Reranker 可插拔架构

### 3.1 整体设计

```
三路检索结果
     │
     ▼
┌─────────────┐
│ 阶段1: RRF  │  ← 永远执行，零成本修正跨源评分
│ 粗排融合     │
└─────┬───────┘
      │
      ▼
  provider=rrf? ───yes──→ 去重 → 输出
      │
      no
      │
      ▼
┌─────────────┐
│ 阶段2: 精排  │  ← BGE 或 Cohere，只处理 top_k 候选
│ 语义重排序   │
└─────┬───────┘
      │
      ▼
   去重 → 输出
```

**RRF 总是第一阶段**，因为它解决了核心问题：Milvus cosine 分数、ES BM25 分数、KG 匹配数三者不可直接比较。RRF 只关心排名，天然跨源可比。

**BGE/Cohere 是第二阶段精排**，输入是 RRF 筛选后的 top-k 候选（默认 20 条），大幅减少计算量。

### 3.2 文件结构

```
app/adapters/reranker/
├── __init__.py          # 导出 BaseReranker, RRF, BGE, Cohere, get_reranker
├── base.py              # BaseReranker 抽象接口
├── rrf.py               # Reciprocal Rank Fusion 实现
├── bge.py               # BGE-reranker-v2-m3 via FlagEmbedding
├── cohere.py            # Cohere Rerank API
└── factory.py           # get_reranker() — 跟 LLM factory 同模式
```

### 3.3 接口定义

```python
# app/adapters/reranker/base.py
from abc import ABC, abstractmethod

class BaseReranker(ABC):
    @abstractmethod
    async def rerank(
        self, query: str, documents: list[dict], top_k: int = 10
    ) -> list[dict]:
        """
        documents: [{"chunk_id": ..., "text": ..., "score": ..., "source": ..., "ranks": {"milvus": 1, "es": 3, ...}}, ...]
        返回: 重排序后的 documents，按新分数降序
        """
        ...
```

### 3.4 RRF 实现

```python
# app/adapters/reranker/rrf.py
class RRFReranker(BaseReranker):
    def __init__(self, k: int = 60):
        self.k = k

    async def rerank(self, query: str, documents: list[dict], top_k: int = 10) -> list[dict]:
        # 按 source 分组，每组内按原始分数排名
        # RRF_score = Σ 1/(k + rank_in_source)
        # 按 RRF_score 降序排列，返回 top_k
        ...
```

### 3.5 BGE 实现

```python
# app/adapters/reranker/bge.py
class BGEReranker(BaseReranker):
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3", use_fp16: bool = True):
        from FlagEmbedding import FlagReranker
        self._model = FlagReranker(model_name, use_fp16=use_fp16)

    async def rerank(self, query: str, documents: list[dict], top_k: int = 10) -> list[dict]:
        pairs = [[query, doc["text"]] for doc in documents]
        scores = await asyncio.to_thread(self._model.compute_score, pairs)
        # 按分数降序排列，返回 top_k
        ...
```

### 3.6 Cohere 实现

```python
# app/adapters/reranker/cohere.py
class CohereReranker(BaseReranker):
    def __init__(self, api_key: str, model: str = "rerank-english-v3.0"):
        import cohere
        self._client = cohere.Client(api_key)
        self._model = model

    async def rerank(self, query: str, documents: list[dict], top_k: int = 10) -> list[dict]:
        response = await asyncio.to_thread(
            self._client.rerank,
            query=query, documents=[d["text"] for d in documents],
            model=self._model, top_n=top_k
        )
        ...
```

### 3.7 Factory

```python
# app/adapters/reranker/factory.py
def get_reranker() -> BaseReranker:
    provider = settings.reranker_provider  # "rrf" | "bge" | "cohere"

    # 阶段1: RRF 始终创建
    rrf = RRFReranker(k=settings.rrf_k)

    if provider == "rrf":
        return rrf  # 单阶段

    if provider == "bge":
        stage2 = BGEReranker(model_name=settings.reranker_model)
        return TwoStageReranker(rrf, stage2, top_k=settings.reranker_top_k)

    if provider == "cohere":
        stage2 = CohereReranker(api_key=settings.cohere_api_key)
        return TwoStageReranker(rrf, stage2, top_k=settings.reranker_top_k)
```

### 3.8 配置字段

```python
# app/core/config.py 新增
reranker_provider: str = "rrf"       # rrf | bge | cohere
reranker_model: str = "BAAI/bge-reranker-v2-m3"
reranker_top_k: int = 20             # RRF 粗排后取多少条送精排
rrf_k: int = 60                      # RRF 公式常数
cohere_api_key: str = ""
```

```bash
# .env 新增
RERANKER_PROVIDER=rrf
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_K=20
RRF_K=60
COHERE_API_KEY=
```

---

## 4. Executor 集成

### 4.1 当前流程

```
_execute_task() × N (asyncio.gather 并行)
    → 每个 task 调用 router 指定的 tools
    → 返回带 _tool 标签的结果

executor_node()
    → 合并所有 all_hits
    → all_hits.sort(key=score, reverse=True)   ← 问题：跨源分数不可比
    → chunk_id 去重 (保留最高分)
    → 输出
```

### 4.2 新流程

```
_execute_task() × N (asyncio.gather 并行)     ← 不变
    → 每个 task 调用 router 指定的 tools
    → 返回带 _tool 标签的结果 + 按 source 记录排名

executor_node()
    → 合并所有 all_hits
    → 计算每个 source 内的 rank                          ← 新增
    → reranker.rerank(query, all_hits, top_k=10)         ← 新增：两阶段重排
    → chunk_id 去重                                      ← 不变
    → 输出
```

### 4.3 DI 注入

```python
# app/agents/executor.py
def executor_node(state: AgentState) -> AgentState:
    reranker = get_reranker()
    # ... 并行检索 ...
    # ... 计算 source ranks ...
    reranked = await reranker.rerank(state["query"], all_hits, top_k=10)
    # ... 去重 → 输出 ...
```

---

## 5. Health Check 扩容

当前 `GET /admin/health` 检查 PG + Redis + Milvus。Phase 5 新增：

```python
# app/api/v1/admin.py health endpoint
checks = {
    "postgres": await check_pg(),
    "redis": await check_redis(),
    "milvus": await check_milvus(),
    "neo4j": await check_neo4j(),      # 新增
    "elasticsearch": await check_es(),  # 新增
}
# 任一失败 → status: "degraded"，详情在 checks 中标注
```

降级策略：Neo4j/ES 不可用时 API 仍正常运行（仅 KG/Keyword 检索路径降级），health 返回 `degraded` 而非 `unhealthy`。

---

## 6. 空 `__init__.py` 修正

两个文件当前为空（0 bytes），功能不受影响但不利于代码导航：

- `app/ingestion/graph_path/__init__.py` — 导出 `EntityExtractor`, `RelationExtractor`, `Neo4jWriter`
- `app/ingestion/keyword_path/__init__.py` — 导出 `ESWriter`

---

## 7. 测试计划

### 7.1 单元测试

```
tests/unit/adapters/reranker/
├── test_rrf.py              # RRF 公式正确性、跨源排名融合
├── test_bge.py              # BGE mock，验证调用正确
├── test_cohere.py           # Cohere mock，验证调用正确
└── test_factory.py          # 三个 provider 分别创建正确实例

tests/unit/agents/
└── test_executor_rerank.py  # Executor 集成 reranker（mock reranker）
```

### 7.2 集成测试

```
tests/integration/
├── conftest.py                  # skipif: Neo4j/ES/Milvus 是否可达
├── test_neo4j_end_to_end.py     # entity 创建→relation 关联→KG 搜索命中
├── test_elasticsearch_end_to_end.py  # doc 写入→IK 分词→keyword 搜索召回
├── test_three_way_retrieval.py  # 同一 query 三路并行→RRF 融合排序
└── test_reranker.py             # BGE 真实模型重排序
```

- 用 pytest marker `integration` 隔离
- conftest `skipif` 服务不可达则 skip，不影响日常单元测试
- 降级测试留在 unit tests（mock 已够用）

### 7.3 运行方式

```bash
# 启动全量服务
docker compose up -d

# 等待所有服务 healthy
docker compose ps

# 跑集成测试
pytest tests/integration/ -m integration -v

# 日常单元测试（无需 Neo4j/ES）
pytest tests/unit/ -q
```

---

## 8. 依赖变更

```toml
# pyproject.toml 新增
"FlagEmbedding>=1.2.0",    # BGE reranker（provider=bge 时需要）
"cohere>=5.0.0",           # Cohere rerank（provider=cohere 时需要）
```

两个都是可选依赖 — 默认 `provider=rrf` 不需要任何额外依赖。

---

## 9. 实现顺序

| SP | 内容 | 新增文件 | 修改文件 | 验证 |
|----|------|---------|---------|------|
| SP0 | Docker 部署 + config + health + `__init__.py` | 0 | ~6 | `docker compose ps` 全 healthy |
| SP1 | Reranker 架构（base/rrf/bge/cohere/factory） | ~6 | config, DI | 单元测试 |
| SP2 | Executor 两阶段重排序集成 | 0 | executor.py | 单元测试 |
| SP3 | 集成测试 | ~5 | 0 | `pytest tests/integration/ -m integration` |

---

## 10. 降级策略

| 场景 | 行为 |
|------|------|
| Neo4j 不可用 | KG 路径静默跳过，Milvus+ES 继续，health `degraded` |
| ES 不可用 | Keyword 路径静默跳过，Milvus+KG 继续，health `degraded` |
| BGE 模型下载失败 | 回退到纯 RRF，日志警告 |
| Cohere API 超时 | 回退到 RRF 结果，日志警告 |
| 全部检索不可用 | 降级到 memory-only 模式（已有） |

---

## 11. 风险与假设

| 风险 | 缓解措施 |
|------|---------|
| BGE 模型 1.5GB 下载慢 | 默认 `rrf`，BGE 是可选升级 |
| Docker Desktop Windows 无 GPU | BGE CPU 推理，top_k=20 下延迟可控（~200ms） |
| ES IK 分词镜像构建失败 | `Dockerfile.es` 已验证可从官方源安装 |
| Neo4j 首次启动慢 | healthcheck retries=5，给充足启动时间 |

[[project-overview]] [[phase4-status]] [[key-arch-decisions]] [[known-issues]]