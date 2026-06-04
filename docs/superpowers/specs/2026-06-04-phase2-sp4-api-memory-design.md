# Phase 2 SP4: API + Memory — 设计文档

> 日期: 2026-06-04
> 状态: 已确认
> 项目: AgentRAGProject
> 父文档: docs/superpowers/specs/2026-06-02-adaptive-agent-rag-design.md

---

## 1. 概述

### 1.1 目标

补全 Session/Feedback/Memory API 端点 + Memory 模块（Short-term Redis + Long-term PG+Milvus）。

### 1.2 范围

| 模块 | 内容 |
|------|------|
| `app/memory/` | base.py (ABC), conversation.py (Redis 短期记忆), long_term.py (PG+Milvus 长期记忆) |
| `app/api/v1/sessions.py` | POST/GET/DELETE sessions + GET history |
| `app/api/v1/feedbacks.py` | POST/GET feedback by trace_id + GET stats |
| `app/api/v1/memories.py` | GET/search/POST/DELETE memories |
| `app/services/` | session_service, feedback_service, memory_service |
| `app/core/di.py` | get_redis() 惰性单例 |

### 1.3 非范围

- `app/memory/working.py` — AgentState 已是 working memory
- `app/memory/reflection.py` — 记忆巩固需 Agent 集成，Phase 3
- PATCH memories, DELETE corrected, POST export — 边缘场景
- Admin stats/logs/routes — Phase 3
- security_service.py — Phase 3

---

## 2. 架构

### 2.1 依赖链

```
app/api/v1/sessions.py → session_service → Session (PG) + ConversationMemory (Redis)
app/api/v1/feedbacks.py → feedback_service → Feedback (PG)
app/api/v1/memories.py → memory_service → LongTermMemoryStore (PG + Milvus)
```

### 2.2 目录变更

```
app/
├── memory/                  ← 新增模块
│   ├── __init__.py
│   ├── base.py              # BaseMemoryStore ABC
│   ├── conversation.py      # ConversationMemory → Redis
│   └── long_term.py         # LongTermMemoryStore → PG + Milvus
├── api/v1/
│   ├── sessions.py          ← 新增
│   ├── feedbacks.py         ← 新增
│   ├── memories.py          ← 新增
│   └── router.py            ← 修改: 注册新路由
├── services/
│   ├── session_service.py   ← 新增
│   ├── feedback_service.py  ← 新增
│   └── memory_service.py    ← 新增
└── core/
    └── di.py                ← 修改: +get_redis()
```

---

## 3. Redis DI

```python
# app/core/di.py — 追加
import redis.asyncio as aioredis

_redis_client: aioredis.Redis | None = None

async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client
```

---

## 4. Memory 模块

### 4.1 BaseMemoryStore ABC

```python
# app/memory/base.py
from abc import ABC, abstractmethod

class BaseMemoryStore(ABC):
    @abstractmethod
    async def asave(self, key: str, data: dict, ttl: int | None = None) -> None: ...
    @abstractmethod
    async def aload(self, key: str) -> dict | None: ...
    @abstractmethod
    async def adelete(self, key: str) -> None: ...
```

### 4.2 ConversationMemory (Short-term → Redis)

Redis key 结构（设计 spec §5.6）：

| Key | Value | TTL |
|-----|-------|-----|
| `session:{id}:summary` | 压缩对话摘要 (str) | 24h |
| `session:{id}:topic` | 当前话题 (str) | 24h |
| `session:{id}:facts` | 已确认事实 (JSON) | 24h |
| `session:{id}:window` | 最近10条消息 (JSON) | 24h |

```python
# app/memory/conversation.py
import json
from app.memory.base import BaseMemoryStore

class ConversationMemory(BaseMemoryStore):
    def __init__(self, redis):
        self.redis = redis

    async def asave(self, key, data, ttl=86400):
        await self.redis.set(key, json.dumps(data, default=str), ex=ttl)

    async def aload(self, key):
        raw = await self.redis.get(key)
        return json.loads(raw) if raw else None

    async def adelete(self, key):
        await self.redis.delete(key)

    # Convenience methods
    async def save_summary(self, session_id, summary): ...
    async def save_topic(self, session_id, topic): ...
    async def save_facts(self, session_id, facts): ...
    async def save_window(self, session_id, messages): ...
    async def get_context(self, session_id) -> dict: ...  # 聚合返回
```

### 4.3 LongTermMemoryStore (Long-term → PG + Milvus)

```python
# app/memory/long_term.py
class LongTermMemoryStore:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id, type, content, confidence=1.0, ...) -> LongTermMemory:
        # 1. 生成 embedding (OpenAIEmbedding)
        # 2. 写入 PG
        # 3. 异步写入 Milvus memories collection (best-effort)
        ...

    async def search_by_embedding(self, query, user_id, top_k=10) -> list[LongTermMemory]:
        # Milvus 语义搜索 → 用 memory_id 回查 PG
        ...

    async def list_by_user(self, user_id, type=None, limit=50) -> list[LongTermMemory]: ...
    async def get(self, memory_id) -> LongTermMemory | None: ...
    async def delete(self, memory_id) -> None: ...
```

---

## 5. API 端点

### 5.1 Sessions

| Method | Path | 请求体 | 响应 |
|--------|------|--------|------|
| POST | `/api/v1/sessions` | `{collection_id?, title?}` | `SessionResponse` |
| GET | `/api/v1/sessions/{id}` | — | `SessionResponse` |
| DELETE | `/api/v1/sessions/{id}` | — | 204 |
| GET | `/api/v1/sessions/{id}/history` | — | `{messages: [...]}` |

### 5.2 Feedbacks

| Method | Path | 请求体 | 响应 |
|--------|------|--------|------|
| POST | `/api/v1/feedback` | `{trace_id, rating?, feedback_type?, comment?, correction?}` | `FeedbackResponse` |
| GET | `/api/v1/feedback?trace_id=xxx` | — | `FeedbackResponse \| null` |
| GET | `/api/v1/feedback/stats` | — | `{total, avg_rating, by_type}` |

### 5.3 Memories

| Method | Path | 请求体 | 响应 |
|--------|------|--------|------|
| GET | `/api/v1/memories?type=knowledge&limit=50` | — | `[MemoryResponse]` |
| POST | `/api/v1/memories/search` | `{query, type?, top_k?}` | `[MemoryResponse]` |
| POST | `/api/v1/memories` | `{type, content, confidence?}` | `MemoryResponse` |
| DELETE | `/api/v1/memories/{id}` | — | 204 |

---

## 6. 测试策略

| 文件 | 内容 | 用例数 |
|------|------|--------|
| `tests/unit/memory/test_conversation.py` | Mock Redis, 测 save/load/delete + convenience 方法 | 5 |
| `tests/unit/memory/test_long_term.py` | Mock DB + Embedding, 测 create/search/list/delete | 5 |
| `tests/unit/services/test_session_service.py` | Mock DB + ConversationMemory, 测 CRUD | 4 |
| `tests/unit/services/test_feedback_service.py` | Mock DB, 测 create/get/stats | 4 |
| `tests/unit/services/test_memory_service.py` | Mock LongTermMemoryStore, 测 CRUD + search | 4 |
| 扩展 `test_all_imports.py` | 新增模块 import 验证 | ~7 |
| **合计** | | **~29 new + 81 existing = ~110** |

---

## 7. 关键决策

| # | 决策 | 选择 |
|---|------|------|
| 1 | Redis 客户端 | `redis.asyncio.from_url()` 惰性单例 |
| 2 | Memory ABC | 只定义 asave/aload/adelete 三个方法 |
| 3 | ConversationMemory | 直接在类上提供 convenience 方法，不引入额外抽象 |
| 4 | LongTermMemory Milvus write | asyncio.create_task 异步写入，best-effort |
| 5 | 服务层 | 每个 domain 一个 service 文件，不合并 |
| 6 | API 模式 | 跟现有 collections.py 一致：Pydantic models inline，Depends(get_db + get_current_user) |
| 7 | working.py / reflection.py | Phase 3 |