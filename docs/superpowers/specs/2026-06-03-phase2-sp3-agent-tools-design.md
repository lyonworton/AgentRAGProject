# Phase 2 SP3: Agent + Tools 升级 — 设计文档

> 日期: 2026-06-03
> 状态: 已确认
> 项目: AgentRAGProject
> 父文档: docs/superpowers/specs/2026-06-02-adaptive-agent-rag-design.md

---

## 1. 概述

### 1.1 目标

将 Phase 1 的单后端 Agent（仅 Milvus）升级为真正的多后端自适应检索系统。

### 1.2 范围

| 组件 | Phase 1 现状 | SP3 目标 |
|------|-------------|---------|
| Router | 所有路由硬编码为 `"milvus"` | LLM 动态路由，基于 intent 分配 Tool 组合 |
| Executor | 仅处理 milvus，单 collection | 多路径并行调度 + 依赖解析 + 结果归一化 |
| Tools | 不存在 | 3 个 Tool：semantic_search / kg_search / keyword_search |
| 后端 | SP1/SP2 已建好 Neo4j + ES + Milvus | 查询侧正式接入全部三个后端 |

### 1.3 非范围

- web_search Tool — 留给后续迭代
- 下游节点（reflector, verifier, synthesizer）— 不改动
- Graph 结构（节点编排）— 不改动

---

## 2. 架构

### 2.1 整体数据流

```
Query → Understander (intent + subtasks)
  → Router (LLM) → routes: {task_id: ["semantic_search", "kg_search"]}
  → Executor:
      1. 依赖解析 → 拓扑排序分组
      2. 按组串行，组内并行执行 tasks
      3. 每个 task 并行调用其 routes 对应的 Tools
      4. 任意 Tool 失败 → log warning, 继续其他
      5. 归一化 → RetrievedChunk[] (merge + dedup by chunk_id)
  → Reflector / Verifier / Synthesizer (零改动)
```

### 2.2 目录结构

```
app/
├── tools/              ← 新增模块
│   ├── __init__.py     # ToolRegistry + get_tool_registry()
│   ├── base.py         # BaseTool ABC
│   ├── semantic_search.py   # SemanticSearchTool → Milvus
│   ├── kg_search.py         # KGSearchTool → Neo4j
│   └── keyword_search.py    # KeywordSearchTool → ES
├── agents/
│   ├── state.py        ← 修改: routes 类型变更
│   ├── router.py       ← 重写: LLM 动态路由
│   ├── executor.py     ← 重写: 多路径调度 + 归一化
│   ├── understander.py ← 不改
│   ├── reflector.py    ← 不改
│   ├── verifier.py     ← 不改
│   ├── nodes.py        ← 不改
│   └── graph.py        ← 不改
└── services/
    └── agent_service.py ← 修改: routes_used flatten
```

---

## 3. BaseTool 接口

### 3.1 抽象基类

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
        """执行检索，返回统一格式的结果列表。

        每个结果 dict 保证字段:
          - chunk_id: str    唯一标识
          - text: str        检索文本内容
          - score: float     相关性分数
          - source: str      "milvus" | "kg" | "keyword"

        可选字段:
          - document_id: str (milvus/es 有，kg 无)
        """
```

### 3.2 调用约定

- Tool 设置 `source` 字段（标识后端）
- Executor 注入 `_tool` 字段（标识 Tool 名，用于 raw_* 分类）
- `_tool` 不暴露给下游，仅 Executor 内部使用

---

## 4. 三个 Tool

### 4.1 SemanticSearchTool → Milvus

```
流程:
  1. query expansion: LLM 生成 3 个同义变体 (从 executor.py 移入)
  2. 每个 variant × 每个 collection: embed → Milvus.search(col_{id}, top_k=10)
  3. 合并 + 去重 (by chunk_id, 保留最高分)

输出: {chunk_id, document_id, text, score, source="milvus"}

依赖: OpenAIEmbedding + MilvusStore + OpenAILLM (for expansion)
```

### 4.2 KGSearchTool → Neo4j

```
流程:
  1. asearch_entities(query, top_k=10) → 匹配实体
  2. 对 top 5 实体依次 aquery_relations(entity_id) → 展开关系
  3. 文本化:
     实体: "Entity: {name} ({type})"
     关系: "{from} → {TYPE} → {to}"

输出: {chunk_id="kg-entity-{urlsafe_id}"|"kg-rel-{from}-{to}", text, score=0.5, source="kg"}

注意: KG 无原生相似度分数，统一使用 0.5 中性分。
      collection_ids 被忽略 — KG schema 当前不按 collection 分区。
      entity id 使用 urllib.parse.quote(id, safe="") 编码避免特殊字符。

依赖: Neo4jKGStore
```

### 4.3 KeywordSearchTool → Elasticsearch

```
流程:
  1. 每个 collection_id: es.asearch(col_id, query, top_k=10)
  2. 文本截断到 500 字符 (+ "..." 标记)

输出: {chunk_id=document_id, document_id, text(≤500), score, source="keyword"}

依赖: ElasticsearchStore
```

---

## 5. ToolRegistry

```python
# app/tools/__init__.py

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
        _registry = ToolRegistry()
        _registry.register(SemanticSearchTool())
        _registry.register(KGSearchTool())
        _registry.register(KeywordSearchTool())
    return _registry
```

ToolRegistry 同时被 Router（获取 Tool 描述生成 LLM prompt）和 Executor（按名查找 Tool 实例）使用。

---

## 6. Router 设计

### 6.1 从纯函数到 LLM 调用

**当前**: `for task in subtasks: routes[task.id] = "milvus"`（硬编码）

**新设计**: LLM 根据 subtask 描述 + intent + 可用 Tool 列表，动态决定路由。

### 6.2 Prompt

```
你是检索路由专家。根据子任务的描述和意图，决定使用哪些检索工具。

可用工具：
{tool_descriptions}       ← 从 ToolRegistry 动态生成

路由参考：
- fact 意图优先 semantic_search
- relation 意图优先 kg_search
- exact 意图优先 keyword_search
- comparison 意图通常需要 semantic_search + kg_search
- reasoning 意图可能需要所有三个工具

子任务列表：
{tasks_json}              ← 仅含 id, description, intent

输出 JSON 数组：
[{"task_id": "t1", "tools": ["semantic_search"]}, ...]
```

### 6.3 Fallback

```python
FALLBACK_RULES = {
    "fact": ["semantic_search"],
    "relation": ["kg_search"],
    "exact": ["keyword_search"],
    "comparison": ["semantic_search", "kg_search"],
    "reasoning": ["semantic_search", "kg_search", "keyword_search"],
}
```

LLM 调用失败（网络错误、超时等）→ 自动使用 fallback 规则路由。

### 6.4 输出校验

LLM 返回的 Tool 名可能与实际不符（幻觉）。Router 过滤无效 Tool 名后再写入 state：

```python
valid = set(registry.tool_names)
state["routes"] = {
    tid: [t for t in tools if t in valid]
    for tid, tools in routes.items()
}
```

### 6.5 AgentState 类型变更

```python
# app/agents/state.py — 仅改一行
routes: Dict[str, list[str]]  # 原: Dict[str, str]
```

---

## 7. Executor 设计

### 7.1 执行流程

```
Executor 输入: sub_tasks, routes, collection_ids

1. 初始化
   raw_milvus_hits = [], raw_kg_results = [], raw_keyword_hits = []
   warnings = []

2. 依赖校验 + 拓扑排序 → 执行分组
   _resolve_groups(sub_tasks)
   例: [t1→t2,t3→t4] → [["t1"], ["t2","t3"], ["t4"]]

3. 按组串行，组内并行
   for group in groups:
       results = await asyncio.gather(*[
           _execute_task(t, routes, collection_ids, registry)
           for t in group
       ])

4. 归一化
   所有 Tool raw 结果 → RetrievedChunk[]
   merge + dedup by chunk_id + sort by score desc

5. 写入 state
   state["retrieved"] = ...
   state["raw_milvus_hits"] = ...
   state["raw_kg_results"] = ...
   state["raw_keyword_hits"] = ...
   state["warnings"].extend(...)
```

### 7.2 _execute_task

```python
async def _execute_task(task, routes, collection_ids, registry):
    tool_names = routes.get(task["id"], ["semantic_search"])
    task["status"] = "running"
    warnings = []

    results = await asyncio.gather(*[
        registry.get(name).arun(task["description"], collection_ids)
        for name in tool_names
    ], return_exceptions=True)

    hits = []
    for name, result in zip(tool_names, results):
        if isinstance(result, Exception):
            warnings.append(f"Tool {name} failed: {result}")
        else:
            for item in result:
                item["_tool"] = name  # Executor 注入，用于 raw_* 分类
            hits.extend(result)

    task["status"] = "failed" if not hits else "done"
    return hits, warnings
```

### 7.3 依赖解析

```python
def _resolve_groups(sub_tasks: list[dict]) -> list[list[str]]:
    """拓扑排序 → 执行分组。组内无相互依赖，可并行。"""
    # 前置校验：所有依赖引用的 task_id 必须存在
    all_ids = {t["id"] for t in sub_tasks}
    for t in sub_tasks:
        for dep in t.get("depends_on", []):
            if dep not in all_ids:
                raise ValueError(f"Task {t['id']} depends on unknown task {dep}")

    completed = set()
    remaining = {t["id"]: set(t.get("depends_on", [])) for t in sub_tasks}
    groups = []

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

### 7.4 归一化

```python
# Tool raw 结果 → RetrievedChunk
retrieved = []
seen = set()
for hit in sorted(all_hits, key=lambda h: h["score"], reverse=True):
    if hit["chunk_id"] not in seen:
        retrieved.append(RetrievedChunk(
            chunk_id=hit["chunk_id"],
            document_id=hit.get("document_id", ""),
            text=hit["text"],
            score=hit["score"],
            source=hit["source"],    # 下游可见
            metadata={},
        ))
        seen.add(hit["chunk_id"])

# raw_* 分类用 _tool（内部字段）
state["raw_milvus_hits"]   = [h for h in all_hits if h["_tool"] == "semantic_search"]
state["raw_kg_results"]    = [h for h in all_hits if h["_tool"] == "kg_search"]
state["raw_keyword_hits"]  = [h for h in all_hits if h["_tool"] == "keyword_search"]
```

### 7.5 错误处理

- 单个 Tool 调用失败 → log warning，不阻塞其他 Tool
- 单个 subtask 全部 Tool 失败 → status = "failed"，不贡献结果
- 整个 Executor 不抛异常（保持架构决策 #6: error degradation, not blocking）

---

## 8. agent_service.py 适配

```python
# 第 54 行修改
# 原: "routes_used": list(set(result.get("routes", {}").values()))
# 新:
routes = result.get("routes", {})
flat = set()
for tools in routes.values():
    flat.update(tools)
"routes_used": list(flat)
```

---

## 9. 文件清单

### 修改 (4)

| 文件 | 改动 |
|------|------|
| `app/agents/state.py` | `routes: Dict[str, list[str]]` |
| `app/agents/router.py` | 重写：LLM 动态路由 + fallback + 校验 |
| `app/agents/executor.py` | 重写：多路径调度 + 依赖解析 + 归一化 |
| `app/services/agent_service.py` | flatten routes_used |

### 新增 (5)

| 文件 | 内容 |
|------|------|
| `app/tools/__init__.py` | ToolRegistry + get_tool_registry() |
| `app/tools/base.py` | BaseTool ABC |
| `app/tools/semantic_search.py` | SemanticSearchTool |
| `app/tools/kg_search.py` | KGSearchTool |
| `app/tools/keyword_search.py` | KeywordSearchTool |

### 不改 (5)

`understander.py`, `reflector.py`, `verifier.py`, `nodes.py`, `graph.py`

---

## 10. 测试策略

### 新增测试

| 文件 | 内容 | 估计用例数 |
|------|------|-----------|
| `tests/unit/agents/test_router.py` | 重写：Mock LLM，测路由正确性、多路由、fallback、无效 Tool 过滤 | 5 |
| `tests/unit/agents/test_executor.py` | 新增：Mock Tools，测依赖解析(无依赖/线性/菱形/环形)、并行调度、单 Tool 失败隔离、归一化合并 | 6 |
| `tests/unit/tools/test_semantic_search.py` | Mock Milvus+Embedding，测 query expansion、多 collection、去重 | 4 |
| `tests/unit/tools/test_kg_search.py` | Mock Neo4jKGStore，测实体搜索+关系展开、空结果 | 3 |
| `tests/unit/tools/test_keyword_search.py` | Mock ES，测文本截断、多 collection、空结果 | 3 |
| `tests/unit/tools/test_registry.py` | 测注册、查找、未知 Tool 抛异常、descriptions 生成 | 3 |

### 保持通过

- `test_graph.py` (3) — graph.py 不改
- `test_chunker.py` (2) — 不相关
- SP2 测试 (35) — 不相关
- `test_all_imports.py` — 扩展覆盖 `app/tools/`

### 预估: 24 新测试 + 10 现有 + 35 SP2 = 69 全部通过

---

## 11. 确认决策汇总

| # | 决策 | 选择 |
|---|------|------|
| 1 | web_search Tool | MVP 跳过 |
| 2 | 多路径执行策略 | 混合：默认并行 + 依赖感知 |
| 3 | Tool 接口 | 自定义 BaseTool ABC（不用 LangChain BaseTool） |
| 4 | 路由方式 | LLM 动态路由 + 规则 fallback |
| 5 | Tool 目录 | `app/tools/` 顶级模块 |
| 6 | 结果归一化 | 统一 RetrievedChunk 格式 |
| 7 | Query expansion | 移入 SemanticSearchTool 内部 |
| 8 | KG 评分 | 固定 0.5（无原生相似度） |
| 9 | ES 文本 | 截断到 500 字符 |
| 10 | Error 策略 | 单 Tool 失败 → warning → continue |