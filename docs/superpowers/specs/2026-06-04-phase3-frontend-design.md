# Phase 3: 前端 + 生产化 — 设计文档

> 日期: 2026-06-04
> 状态: 已确认
> 项目: AgentRAGProject
> 前置: Phase 2 (SP1-SP4) 全部完成

---

## 1. 概述

Phase 3 交付一个可对外提供服务的完整 RAG 产品：Admin 管理控制台 + User 对话界面 + 生产化基础设施。

### 1.1 核心交付

| 模块 | 描述 | 优先级 |
|------|------|--------|
| Admin UI | 知识库 / 文档 / 摄入源管理 | P0 |
| User Chat UI | 流式对话 + 引文展示 + 用户反馈 | P0 |
| 前端部署 | Nginx 静态文件 + 反向代理到 FastAPI | P1 |

### 1.2 技术选型

| 层 | 技术 |
|----|------|
| 前端框架 | React 18 + TypeScript + Vite 6 |
| UI 组件库 | shadcn/ui (Radix Primitives + Tailwind CSS) |
| 路由 | React Router v6 (React.lazy route-based code splitting) |
| 服务端数据 | 简单 fetch hooks (useState + useEffect + loading/error) |
| 客户端状态 | React Context (认证信息) |
| 流式通信 | fetch + ReadableStream (SSE 解析) |
| 前端部署 | Nginx 静态文件 + 反向代理到 FastAPI |

---

## 2. 前端架构

### 2.1 单一应用 + 路由分层

```
frontend/
├── src/
│   ├── main.tsx                  # 入口
│   ├── App.tsx                   # React Router 路由分发
│   ├── api/                      # API client + fetch hooks
│   │   ├── client.ts             # fetch wrapper (base URL, auth header)
│   │   ├── collections.ts
│   │   ├── documents.ts
│   │   ├── ingestion.ts
│   │   ├── queries.ts            # + SSE stream helper
│   │   ├── sessions.ts
│   │   ├── feedbacks.ts
│   │   └── auth.ts
│   ├── components/               # 共享 UI 组件
│   │   ├── layout/               # AppShell, Sidebar, Header
│   │   ├── ui/                   # shadcn/ui 组件 (button, card, dialog, ...)
│   │   └── shared/               # 业务共享 (StatusBadge, EmptyState, ...)
│   ├── routes/
│   │   ├── admin/                # /admin/*
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Collections.tsx
│   │   │   ├── CollectionDetail.tsx
│   │   │   └── Ingestion.tsx
│   │   └── chat/                 # /chat/*
│   │       ├── ChatView.tsx      # 主对话界面
│   │       └── SessionList.tsx   # 历史会话列表
│   ├── hooks/                    # 自定义 hooks
│   └── lib/                      # 工具函数 (cn, formatDate, ...)
├── vite.config.ts
├── tailwind.config.ts
├── components.json               # shadcn/ui 配置
├── tsconfig.json
└── package.json
```

### 2.2 路由表

```
/login                       → 登录页 (admin 和 chat 共用)
/admin                       → Dashboard 仪表盘
/admin/collections           → 知识库列表
/admin/collections/:id       → 知识库详情 + 文档列表
/admin/ingestion             → 摄入源配置 (本地/网页/数据库)
/admin/ingestion/jobs        → 摄入任务列表
/chat                        → ChatView (最近活跃会话)
/chat/:sessionId             → ChatView (指定会话)
```

### 2.3 数据流

```
React Component → fetch hook (useState + useEffect) → fetch(/api/v1/...) → FastAPI
                                                                  │
[流式] User 输入 → POST /api/v1/query/stream ─────────────────────┘
                                                                  │
React state ← SSE event: chunk → 逐 token 渲染 + 引文侧栏 ←──────┘
```

### 2.4 构建产物与部署

```
frontend/dist/
├── index.html
├── assets/
│   ├── index-abc123.js      # 主 bundle (~200KB gzipped)
│   ├── admin-def456.js      # Admin 懒加载 chunk
│   └── chat-ghi789.js       # Chat 懒加载 chunk
```

Nginx 路由规则:
```
location /              → frontend/dist/  (SPA fallback → index.html)
location /api/          → proxy_pass http://fastapi:8000
```

---

## 3. Admin UI 设计

### 3.1 布局

```
┌──────────────────────────────────────────────────┐
│ Header:  AgentRAG Admin  |  用户头像 ▼           │
├──────────┬───────────────────────────────────────┤
│ Sidebar  │  📊 仪表盘                            │
│          │  ┌─────┬─────┬─────┬─────┐            │
│ 📊 仪表盘│  │集合  │文档  │查询  │任务  │            │
│ 📚 知识库│  │  5   │ 127  │ 340  │  3   │            │
│ 📥 摄入  │  └─────┴─────┴─────┴─────┘            │
│ 📋 任务  │                                       │
│          │  最近查询                              │
│          │  ┌──────────────────────────────┐     │
│          │  │ trace_id  | query   | 状态   │     │
│          │  └──────────────────────────────┘     │
└──────────┴───────────────────────────────────────┘
```

### 3.2 页面清单

#### 3.2.1 Dashboard (`/admin`)

- 4 张统计卡片: 知识库总数 / 文档总数 / 今日查询数 / 摄入任务数
- 最近查询列表 (trace_id, query, latency, status)
- 最近摄入任务 (job_id, 进度条, status badge)

#### 3.2.2 知识库列表 (`/admin/collections`)

- Table: 名称 | 文档数 | 分块数 | embedding_model | 状态 | 创建时间
- 操作: 新建 (Dialog 表单) / 删除 (Confirm Dialog) / 点击行进入详情

#### 3.2.3 知识库详情 (`/admin/collections/:id`)

- Tab 1 — **文档**: Table (标题, 类型, 大小, 状态, 摄入时间), 操作 (删除, 重索引)
- Tab 2 — **配置**: 只读字段 (embedding_model, chunk_size, 向量维度)
- Tab 3 — **搜索测试**: 输入框 + 结果片段展示 + 相关度分数

#### 3.2.4 摄入 (`/admin/ingestion`)

三种来源的 Tab 表单:

| Tab | 表单字段 | 提交 API |
|-----|---------|---------|
| 本地文件 | 知识库选择 + 拖拽文件区 | POST /api/v1/ingest/local |
| 网页 | 知识库选择 + URL 列表 (textarea) | POST /api/v1/ingest/web |
| 数据库 | 知识库选择 + 连接串 + 查询 | POST /api/v1/ingest/database |

提交成功后 → 跳转 `/admin/ingestion/jobs` 查看进度

#### 3.2.5 任务管理 (`/admin/ingestion/jobs`)

- Table: job_id | 知识库 | 来源 | 进度 (completed/total) | 状态 badge | 开始时间
- 展开行 → 错误详情 (errors JSON)

---

## 4. User Chat UI 设计

### 4.1 布局

```
┌──────────────────────────────────────────────────────┐
│ Header:  AgentRAG Chat  |  [+ 新会话]  |  会话列表 ≡  │
├────────────┬─────────────────────────────────────────┤
│ 会话列表    │  Messages                              │
│ (可折叠)   │  ┌──────────────────────────────────┐  │
│            │  │ 👤 对比A方案和B方案的扩展性         │  │
│ sess-1    │  └──────────────────────────────────┘  │
│ sess-2    │  ┌──────────────────────────────────┐  │
│ sess-3    │  │ 🤖 A方案支持水平扩展到100+节点...   │  │
│            │  │ [1] chunk_a3f2  [2] chunk_b7d1   │  │
│            │  │ ★★★★☆  反馈: 👍 有用  👎 不准确   │  │
│            │  └──────────────────────────────────┘  │
│            │                                        │
│            │  ┌──────────────────────────────────┐  │
│            │  │ 输入您的问题...          [发送 →] │  │
│            │  └──────────────────────────────────┘  │
└────────────┴─────────────────────────────────────────┘
```

### 4.2 核心功能

#### 4.2.1 流式对话

- 调用 `POST /api/v1/query/stream` (SSE)
- `event: status` → 状态条 (understanding / routing / executing / ...)
- `event: chunk` → 逐 token 追加到消息气泡，光标闪烁
- `event: citation` → 消息底部渲染引文编号 `[1]`
- `event: done` → 显示 trace 摘要 (iterations, quality_score, latency_ms)

#### 4.2.2 引文面板

- 消息中 `[来源: chunk_id]` 渲染为可点击上标链接 `[1]`
- 点击引文 → 右侧滑出面板：原文片段 + 文档标题 + 相关度分数
- 面板底部链接: "查看完整文档"

#### 4.2.3 用户反馈

- 每条 AI 消息底部: 👍 有用 / 👎 不准确
- 点击后弹出可选文字输入
- 提交 `POST /api/v1/feedback` → 按钮变灰禁用

#### 4.2.4 会话管理

- 左侧会话列表: 标题 (或默认截取首条消息) + 最后活动时间
- 新建会话 → `POST /api/v1/sessions`
- 删除会话 → `DELETE /api/v1/sessions/:id`
- 点击会话 → 加载历史消息 `GET /api/v1/sessions/:id/history`

---

## 5. 前端部署

### 5.1 Nginx 配置

```
server {
    listen 3000;
    root /app/dist;
    location / {
        try_files $uri /index.html;    # SPA fallback
    }
    location /api/ {
        proxy_pass http://fastapi:8000;
    }
}
```

### 5.2 Docker Compose 新增

```yaml
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [fastapi]
```

### 5.3 前端使用的后端 API

| 路由 | HTTP | 前端位置 |
|------|------|---------|
| `/auth/login` | POST | Login page |
| `/collections` | GET/POST | Admin: 知识库列表 |
| `/collections/:id` | DELETE | Admin: 删除知识库 |
| `/collections/:id/config` | GET | Admin: 配置 Tab |
| `/collections/:id/search` | POST | Admin: 搜索测试 Tab |
| `/collections/:id/documents` | GET | Admin: 文档列表 Tab |
| `/collections/:id/documents/:did` | DELETE | Admin: 删除文档 |
| `/collections/:id/documents/:did/reindex` | POST | Admin: 重索引 |
| `/ingest/local` | POST | Admin: 本地文件摄入 |
| `/ingest/web` | POST | Admin: 网页摄入 |
| `/ingest/database` | POST | Admin: DB 摄入 |
| `/ingest/:job_id` | GET | Admin: 任务状态 |
| `/query` | POST | Chat: 非流式查询 |
| `/query/stream` | POST | Chat: 流式查询 (SSE) |
| `/query/:trace_id/trace` | GET | Chat: 查询回溯 |
| `/sessions` | POST | Chat: 新建会话 |
| `/sessions/:id` | GET/DELETE | Chat: 会话操作 |
| `/sessions/:id/history` | GET | Chat: 加载历史 |
| `/feedback` | POST | Chat: 提交反馈 |

---

## 6. 测试策略

| 层 | 内容 | 工具 |
|----|------|------|
| 前端单元 | 组件渲染、hooks 逻辑 | Vitest + React Testing Library + vi.mock |
| 手动验证 | Admin CRUD + Chat 多轮对话 | chrome-devtools-mcp (已有) |

---

## 8. MVP 范围外 (明确不做)

- 响应式移动端适配 (桌面版优先)
- 国际化 i18n
- 深色模式
- Admin 用户管理页 (CRUD 用户/权限)
- Admin 系统配置页 (provider 管理 → .env 足够 MVP)
- OAuth / 社交登录
- 实时通知 (WebSocket)

---

## 9. 关键设计决策

| 决策 | 理由 |
|------|------|
| 单一前端应用 | 两个应用 2x 复杂度无 MVP 收益，共享组件和 API client |
| Admin 先于 Chat | Admin 造数据 → Chat 消费, 依赖顺序正确 |
| shadcn/ui | Dashboard 组件优 + Tailwind 原子化 + tree-shakable |
| 简单 fetch hooks | 无状态库依赖: useState+useEffect+loading/error, 减少 30KB bundle |
| Nginx 静分 + 反向代理 | 无需 Node.js 服务端, 静态文件直出 |
| 跳过 MinIO/Prometheus/Grafana | MVP 阶段本地文件系统+structlog 足够, 生产化是 Phase 4 任务 |
| React.lazy 路由分块 | 自动代码分割, Admin/Chat chunk 按需加载 |