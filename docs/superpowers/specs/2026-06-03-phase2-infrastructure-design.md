# Sub-project 1: 基础设施 — 设计文档

> 日期: 2026-06-03
> 状态: 已确认
> 父规格: docs/superpowers/specs/2026-06-02-adaptive-agent-rag-design.md
> Phase: 2 (Week 4)

---

## 1. 概述

Sub-project 1 的目标是为 Phase 2 的三路检索和记忆系统搭建基础设施底座。交付物包括：

1. Docker Compose 扩展（Neo4j + Elasticsearch 服务）
2. KG 适配器（Neo4j 图数据库抽象）
3. ES 适配器（Elasticsearch 全文检索抽象，含 IK 中文分词）
4. 完整的数据模型 + Alembic 迁移（10 张新表 + 已有 5 张表的初始迁移）

---

## 2. Docker Compose 变更

在现有服务（postgres, etcd, minio, milvus, redis, fastapi, arq-worker）基础上新增：

```yaml
neo4j:
  image: neo4j:5
  ports: ["7474:7474", "7687:7687"]
  environment:
    NEO4J_AUTH: neo4j/${NEO4J_PASSWORD:-agentrag123}
  volumes: [neo4jdata:/data]
  healthcheck:
    test: ["CMD-SHELL", "cypher-shell -u neo4j -p $${NEO4J_PASSWORD:-agentrag123} 'RETURN 1' || exit 1"]

elasticsearch:
  build:
    context: .
    dockerfile: Dockerfile.es
  ports: ["9200:9200"]
  environment:
    discovery.type: single-node
    xpack.security.enabled: false
    ES_JAVA_OPTS: -Xms1g -Xmx1g
  volumes: [esdata:/usr/share/elasticsearch/data]

volumes:
  neo4jdata:
  esdata:
```

> **注意**: Neo4j healthcheck 使用 `CMD-SHELL` 而非 `CMD`，因为需要 shell 变量展开 `$${NEO4J_PASSWORD}`（`$$` 是 docker-compose 转义，运行时变成 `$`）。

### Dockerfile.es（ES + IK 分词插件）

```dockerfile
FROM elasticsearch:8.12.0
RUN elasticsearch-plugin install --batch \
    https://github.com/infinilabs/analysis-ik/releases/download/v8.12.0/elasticsearch-analysis-ik-8.12.0.zip
```

> IK 插件不在 Elastic 官方仓库中，`elasticsearch-plugin install analysis-ik` 不可用，必须用 URL 安装。

---

## 3. KG 适配器

### 目录结构

```
app/adapters/kg/
├── __init__.py
├── base.py          # BaseKGStore ABC
└── neo4j.py         # Neo4jKGStore 实现
```

### BaseKGStore 抽象

```python
from abc import ABC, abstractmethod

class BaseKGStore(ABC):
    @abstractmethod
    async def aconnect(self) -> None: ...
    @abstractmethod
    async def adisconnect(self) -> None: ...
    @abstractmethod
    async def acreate_graph(
        self, doc_id: str, entities: list[dict], relations: list[dict]
    ) -> None: ...
    @abstractmethod
    async def asearch_entities(self, query: str, top_k: int = 10) -> list[dict]: ...
    @abstractmethod
    async def aquery_relations(
        self, entity_id: str, relation_type: str | None = None
    ) -> list[dict]: ...
    @abstractmethod
    async def adelete_document(self, doc_id: str) -> None: ...
```

### Neo4j 图模型

- 节点：`:Document {id, title}`, `:Entity {id, name, type, aliases}`, `:Chunk {id, text}`
- 关系：`:HAS_CHUNK`, `:REFERENCES`, `:MENTIONED_IN`, `:RELATED_TO {type}`, `:LINKS_TO`

实现使用 `neo4j.AsyncGraphDatabase`。

---

## 4. ES 适配器

### 目录结构

```
app/adapters/search/
├── __init__.py
├── base.py          # BaseSearchStore ABC
└── elasticsearch.py # ElasticsearchStore 实现
```

### BaseSearchStore 抽象

```python
from abc import ABC, abstractmethod

class BaseSearchStore(ABC):
    @abstractmethod
    async def aconnect(self) -> None: ...
    @abstractmethod
    async def adisconnect(self) -> None: ...
    @abstractmethod
    async def acreate_index(self, collection_id: str) -> None: ...
    @abstractmethod
    async def aindex_document(
        self, collection_id: str, doc_id: str, title: str,
        content: str, metadata: dict
    ) -> None: ...
    @abstractmethod
    async def asearch(
        self, collection_id: str, query: str,
        fields: list[str] | None = None, top_k: int = 10,
        filters: dict | None = None
    ) -> list[dict]: ...
    @abstractmethod
    async def adelete_document(
        self, collection_id: str, doc_id: str
    ) -> None: ...
    @abstractmethod
    async def adelete_index(self, collection_id: str) -> None: ...
```

### IK 分词索引 Mapping

```json
{
  "settings": {
    "analysis": {
      "analyzer": {
        "ik_max_word_analyzer": {"type": "custom", "tokenizer": "ik_max_word"},
        "ik_smart_analyzer": {"type": "custom", "tokenizer": "ik_smart"}
      }
    }
  },
  "mappings": {
    "properties": {
      "document_id": {"type": "keyword"},
      "title": {"type": "text", "analyzer": "ik_max_word_analyzer", "search_analyzer": "ik_smart_analyzer"},
      "content": {"type": "text", "analyzer": "ik_max_word_analyzer", "search_analyzer": "ik_smart_analyzer"},
      "section_path": {"type": "keyword"},
      "page_number": {"type": "integer"},
      "source_type": {"type": "keyword"},
      "ingested_at": {"type": "date"}
    }
  }
}
```

索引命名：`col_{collection_id}`

---

## 5. 数据模型

### 现有模式规范

Phase 1 建立了以下约定，所有新模型必须遵循：

- **主键**: `Mapped[str] = mapped_column(String(16), primary_key=True, default=new_uuid)`
- **外键**: `Mapped[str] = mapped_column(String(16), index=True)` （不显式声明 ForeignKey，靠类型约定）
- **可空外键**: `Mapped[str | None] = mapped_column(String(16), nullable=True)`
- **时间戳**: 继承 `TimestampMixin` 获得 `created_at` + `updated_at`；不需要 `updated_at` 的表手动写 `created_at`
- **JSONB**: `Mapped[dict] = mapped_column(JSONB, default=dict)`
- **导入**: `from app.domain.base import Base, TimestampMixin, new_uuid`

### 5.1 sessions

```python
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.domain.base import Base, TimestampMixin, new_uuid

class Session(Base, TimestampMixin):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(16), index=True)
    collection_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # created_at, updated_at from TimestampMixin
```

### 5.2 messages

```python
from sqlalchemy import String, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.domain.base import Base, TimestampMixin, new_uuid

class Message(Base, TimestampMixin):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(String(16), index=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role: Mapped[str] = mapped_column(String(16))       # "user" | "assistant" | "system"
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # created_at from TimestampMixin
```

### 5.3 query_traces

```python
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.domain.base import Base, new_uuid

class QueryTrace(Base):
    __tablename__ = "query_traces"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_uuid)
    session_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    user_id: Mapped[str] = mapped_column(String(16), index=True)
    collection_ids: Mapped[dict] = mapped_column(JSONB, default=dict)
    query: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    citations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    agent_graph: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    iterations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    # 不需要 updated_at（trace 一旦写入不可变）
```

### 5.4 feedbacks

```python
from sqlalchemy import String, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.domain.base import Base, TimestampMixin, new_uuid

class Feedback(Base, TimestampMixin):
    __tablename__ = "feedbacks"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_uuid)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)  # 业务 trace_id，非 FK
    user_id: Mapped[str] = mapped_column(String(16), index=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)          # 1-5
    feedback_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # "correction" | "rating" | "flag"
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction: Mapped[str | None] = mapped_column(Text, nullable=True)            # 用户提供的正确答案
    resolved_status: Mapped[str] = mapped_column(String(16), default="pending")    # pending | reviewed | applied
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # created_at, updated_at from TimestampMixin
```

### 5.5 long_term_memories

```python
from sqlalchemy import String, Float, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.domain.base import Base, TimestampMixin, new_uuid

class LongTermMemory(Base, TimestampMixin):
    __tablename__ = "long_term_memories"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(16), index=True)
    type: Mapped[str] = mapped_column(String(16))                  # "knowledge" | "experience" | "profile"
    entity: Mapped[str | None] = mapped_column(String(256), nullable=True)
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")   # active | corrected | archived
    corrected_by: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # created_at, updated_at from TimestampMixin
```

### 5.6 source_configs

```python
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.domain.base import Base, TimestampMixin, new_uuid

class SourceConfig(Base, TimestampMixin):
    __tablename__ = "source_configs"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(16), index=True)
    source_type: Mapped[str] = mapped_column(String(16))     # "web" | "database"
    name: Mapped[str] = mapped_column(String(256))
    config: Mapped[dict] = mapped_column(JSONB, default=dict)  # URL 列表 / DB 连接信息
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # created_at, updated_at from TimestampMixin
```

### 5.7 provider_configs

```python
from sqlalchemy import String, Boolean, LargeBinary
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.domain.base import Base, TimestampMixin, new_uuid

class ProviderConfig(Base, TimestampMixin):
    __tablename__ = "provider_configs"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(16), index=True)
    provider_type: Mapped[str] = mapped_column(String(16))     # "llm" | "embedding" | "vector-store"
    provider_name: Mapped[str] = mapped_column(String(32))     # "openai" | "ollama" | "milvus"
    config_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)  # 加密存储 API key
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # created_at, updated_at from TimestampMixin
```

### 5.8 system_configs

```python
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime
from app.domain.base import Base, new_uuid

class SystemConfig(Base):
    __tablename__ = "system_configs"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_uuid)
    key: Mapped[str] = mapped_column(String(128), unique=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(16), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # 不需要 created_at（system_config 只有 updated_at）
```

### 5.9 audit_logs

```python
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.domain.base import Base, new_uuid

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_uuid)
    user_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    # 不需要 updated_at（审计日志不可变）
```

### 5.10 user_quotas

```python
from datetime import datetime
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.domain.base import Base, TimestampMixin, new_uuid

class UserQuota(Base, TimestampMixin):
    __tablename__ = "user_quotas"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(16), index=True)
    quota_type: Mapped[str] = mapped_column(String(16))     # "token" | "request" | "storage"
    limit_value: Mapped[int] = mapped_column(Integer)
    used_value: Mapped[int] = mapped_column(Integer, default=0)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # created_at, updated_at from TimestampMixin
```

### 时间戳策略汇总

| 表 | created_at | updated_at | 来源 |
|----|-----------|-----------|------|
| sessions | ✓ | ✓ | TimestampMixin |
| messages | ✓ | ✓ | TimestampMixin |
| query_traces | ✓ 手动 | ✗ | 不可变 |
| feedbacks | ✓ | ✓ | TimestampMixin |
| long_term_memories | ✓ | ✓ | TimestampMixin |
| source_configs | ✓ | ✓ | TimestampMixin |
| provider_configs | ✓ | ✓ | TimestampMixin |
| system_configs | ✗ | ✓ 手动 | 特殊 |
| audit_logs | ✓ 手动 | ✗ | 不可变 |
| user_quotas | ✓ | ✓ | TimestampMixin |

---

## 6. Alembic 迁移

### 策略

Phase 1 没有生成过迁移文件（`alembic/versions/` 为空）。因此使用**单文件合并迁移**：一个 migration 创建全部 15 张表 + 索引。

### 文件: `alembic/versions/001_initial_all.py`

```python
"""initial_all_tables

Revision ID: 001
Create Date: 2026-06-03

All 15 tables: Phase 1 (users, collections, documents, ingest_jobs)
+ Phase 2 (10 new tables) + indexes
"""
```

迁移必须包含：

```sql
-- 第一步：启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- Phase 1 表: users, collections, documents, ingest_jobs
-- Phase 2 表: sessions, messages, query_traces, feedbacks,
--              long_term_memories, source_configs, provider_configs,
--              system_configs, audit_logs, user_quotas
```

### 索引

```sql
-- Phase 1 表索引
CREATE INDEX idx_collections_owner ON collections(owner_id);
CREATE INDEX idx_documents_collection ON documents(collection_id, status);

-- Phase 2 新增索引
CREATE INDEX idx_sessions_user ON sessions(user_id, is_active);
CREATE INDEX idx_messages_session ON messages(session_id, created_at);
CREATE INDEX idx_query_traces_session ON query_traces(session_id, created_at);
CREATE INDEX idx_query_traces_user ON query_traces(user_id, created_at);
CREATE INDEX idx_feedbacks_trace ON feedbacks(trace_id);
CREATE INDEX idx_feedbacks_user ON feedbacks(user_id);
CREATE INDEX idx_memories_user_type ON long_term_memories(user_id, type, status);
CREATE INDEX idx_memories_embedding ON long_term_memories
  USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_ingest_jobs_collection ON ingest_jobs(collection_id, status);
CREATE INDEX idx_source_configs_user ON source_configs(user_id, source_type);
CREATE INDEX idx_provider_configs_user ON provider_configs(user_id, provider_type);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id, created_at);
CREATE INDEX idx_user_quotas_user ON user_quotas(user_id, quota_type);
```

> ivfflat 索引需要在数据量较大时才有效果，创建在空表上不影响功能。

---

## 7. 配置变更

### app/core/config.py

在现有 `Settings` 类中新增字段（不新建类，遵循现有单 Settings 模式）：

```python
class Settings(BaseSettings):
    # === 现有字段 ===
    ...

    # === Phase 2 新增 ===
    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "agentrag123"

    # Elasticsearch
    es_host: str = "http://localhost:9200"

    model_config = {"env_file": ".env", "case_sensitive": False}
```

### app/core/di.py

新增两个依赖注入函数：

```python
from app.adapters.kg.neo4j import Neo4jKGStore
from app.adapters.search.elasticsearch import ElasticsearchStore

_kg_store: Neo4jKGStore | None = None
_search_store: ElasticsearchStore | None = None

async def get_kg_store() -> Neo4jKGStore:
    global _kg_store
    if _kg_store is None:
        _kg_store = Neo4jKGStore()
        await _kg_store.aconnect()
    return _kg_store

async def get_search_store() -> ElasticsearchStore:
    global _search_store
    if _search_store is None:
        _search_store = ElasticsearchStore()
        await _search_store.aconnect()
    return _search_store
```

### app/core/events.py

在 `on_startup` 中增加 Neo4j + ES 连通性预热，在 `on_shutdown` 中增加连接关闭：

```python
async def on_startup():
    logger.info("app starting", env=get_settings().app_env)
    # Phase 2: 预热 Neo4j + ES 连接（失败不阻塞，仅警告）
    try:
        from app.core.di import get_kg_store, get_search_store
        await get_kg_store()
        logger.info("neo4j connected")
    except Exception as e:
        logger.warning("neo4j unavailable, KG features disabled", error=str(e))
    try:
        await get_search_store()
        logger.info("elasticsearch connected")
    except Exception as e:
        logger.warning("elasticsearch unavailable, keyword search disabled", error=str(e))

async def on_shutdown():
    logger.info("app shutting down")
    # Phase 2: 关闭 Neo4j + ES 连接
    try:
        from app.core.di import _kg_store, _search_store
        if _kg_store:
            await _kg_store.adisconnect()
        if _search_store:
            await _search_store.adisconnect()
    except Exception:
        pass
```

### pyproject.toml 新增依赖

```toml
"neo4j>=5.20.0",
"elasticsearch-py[async]>=8.12.0",
"pgvector>=0.2.0",
```

### .env.example 新增

```bash
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=agentrag123

# Elasticsearch
ES_HOST=http://localhost:9200
```

---

## 8. 文件清单汇总

```
新增 (18 files):
  app/adapters/kg/__init__.py
  app/adapters/kg/base.py
  app/adapters/kg/neo4j.py
  app/adapters/search/__init__.py
  app/adapters/search/base.py
  app/adapters/search/elasticsearch.py
  app/domain/session.py
  app/domain/message.py
  app/domain/query_trace.py
  app/domain/feedback.py
  app/domain/long_term_memory.py
  app/domain/source_config.py
  app/domain/provider_config.py
  app/domain/system_config.py
  app/domain/audit_log.py
  app/domain/user_quota.py
  Dockerfile.es
  alembic/versions/001_initial_all.py

修改 (7 files):
  docker-compose.yml
  pyproject.toml
  .env.example
  app/core/config.py
  app/core/di.py
  app/core/events.py
  app/domain/__init__.py
```

---

## 9. 验证标准

1. `docker compose build elasticsearch` → ES+IK 镜像构建成功
2. `docker compose up -d neo4j elasticsearch` → 两个服务健康启动
3. `python -c "from app.adapters.kg.neo4j import Neo4jKGStore; print('OK')"` → 导入成功
4. `python -c "from app.adapters.search.elasticsearch import ElasticsearchStore; print('OK')"` → 导入成功
5. `python -c "from app.domain.session import Session; from app.domain.message import Message; print('OK')"` → 全部 10 个新模型导入成功
6. `alembic upgrade head` → 15 张表全部创建，索引全部生效
7. `pytest tests/ -x -v` → 已有测试仍然通过