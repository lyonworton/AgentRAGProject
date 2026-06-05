# Phase 3: 前端 + 生产化 — 实现计划

> 日期: 2026-06-04
> 状态: 待实施
> 项目: AgentRAGProject
> 前置: Phase 2 (SP1-SP4) 全部完成, 设计 spec 已确认
> 设计 spec: `docs/superpowers/specs/2026-06-04-phase3-frontend-design.md`

---

## 1. 总体策略

按 5 个子项目（SP0-SP4）顺序实施，每 SP 独立可验证。

```
SP0 — 后端补齐 (5 端点 + 3 修改)
SP1 — 前端基础设施 (脚手架 + Auth + Layout + API client)
SP2 — Admin UI (Dashboard + Collections + Ingestion + Jobs)
SP3 — Chat UI (Streaming + Citations + Feedback + Sessions)
SP4 — 部署 (Nginx + Docker Compose + 验证)
```

### 1.1 技术栈

| 层 | 技术 |
|----|------|
| 框架 | React 18 + TypeScript + Vite 6 |
| UI | shadcn/ui (手动复制) + Tailwind CSS 4 |
| 路由 | React Router v6 (React.lazy 代码分割) |
| 状态 | React Context (Auth) + useState/useEffect hooks |
| 流式通信 | fetch + ReadableStream (SSE 解析) |
| 部署 | Nginx 静态文件 + 反向代理 |

### 1.2 关键设计决策

| 决策 | 理由 |
|------|------|
| shadcn/ui 手动复制，不装 CLI | Python 项目生态，加 Node 全局工具增加复杂度 |
| 每页面专用 hook，不做泛型 useFetch | 避免过度抽象，每个 hook 明确返回类型 |
| 懒创建 session（用户发言时才 POST /sessions） | 避免空 session 残留 |
| 不做 TanStack Query/MinIO/Prometheus | 设计 spec 明确 MVP 范围外 |
| 每个数据视图使用统一的 4 态模式 | loading / error / empty / data |

---

## 2. SP0: 后端补齐

**目标**: 补齐前端需要的 API 端点，所有现有测试不退化。

### 2.1 新增端点

| 文件 | 端点 | 方法 | 说明 |
|------|------|------|------|
| `app/api/v1/collections.py` | `/{col_id}` | GET | 返回单个 Collection（含 config dict），404+鉴权 |
| `app/api/v1/ingestion.py` | `` | GET | `?collection_id=&limit=50` 列 IngestJob 列表 |
| `app/api/v1/ingestion.py` | `/web` | POST | Body: `{collection_id, urls: list[str]}`，enqueue web 摄入 |
| `app/api/v1/ingestion.py` | `/database` | POST | Body: `{collection_id, db_url, query, title_column, content_columns}`，enqueue DB 摄入 |
| `app/api/v1/sessions.py` | `` | GET | 列当前用户所有活跃 Session |

### 2.2 修改

| 文件 | 修改 |
|------|------|
| `app/api/v1/collections.py` | `CollectionResponse` 加 `config: dict` 字段 |
| `app/api/v1/queries.py` | ① `done` SSE 事件加 `citations` 字段<br>② 查询完成后调 `session_service.add_message()` 持久化 user+assistant 消息 |
| `app/services/session_service.py` | 新增 `list_sessions(db, user_id) -> list[Session]` |

### 2.3 验证

```
pytest tests/ -x -q          # 81 现有测试不退化
curl POST /api/v1/ingest/web # 返回 {job_id, arq_job_id}
curl GET /api/v1/sessions     # 返回 Session[]
```

---

## 3. SP1: 前端基础设施

**目标**: `npm run dev` 可访问，登录流程可用，Layout 导航可切换。

### 3.1 文件清单

```
frontend/
├── package.json              # react 18, react-router-dom 6, tailwindcss 4,
│                             #   @tailwindcss/vite, lucide-react,
│                             #   class-variance-authority, clsx, tailwind-merge
├── vite.config.ts            # @vitejs/plugin-react + tailwindcss() + proxy /api→:8000
├── tsconfig.json             # strict, paths @/ → src/
├── tsconfig.app.json
├── index.html                # <div id="root"> + <script src="/src/main.tsx">
└── src/
    ├── main.tsx              # ReactDOM.createRoot
    ├── App.tsx                # BrowserRouter + Routes + AuthProvider
    ├── index.css             # @import "tailwindcss" + shadcn CSS variables
    ├── lib/
    │   └── utils.ts          # cn() = clsx + tailwind-merge
    ├── api/
    │   ├── client.ts         # fetch 包装: base URL, auth header, 401→/login, 204→undefined
    │   └── auth.ts           # login(), register()
    ├── context/
    │   └── AuthContext.tsx    # { token, user, login, logout, isAuthenticated }
    ├── components/
    │   ├── ui/               # shadcn 组件: button, input, card, label, dialog, badge,
    │   │                     #   tabs, table, textarea, progress, select, spinner
    │   └── layout/
    │       ├── AppShell.tsx   # flex h-screen: Sidebar + (Header + <Outlet>)
    │       ├── Sidebar.tsx    # NavLink: 仪表盘/知识库/摄入/任务
    │       └── Header.tsx     # 标题 + 用户名 + 登出
    └── routes/
        ├── LoginPage.tsx      # username + password → POST /auth/login → 跳 /admin
        ├── admin/             # (lazy) 空壳占位
        └── chat/              # (lazy) 空壳占位
```

### 3.2 API Client 模式

```typescript
// src/api/client.ts — 纯函数，不建 class
const BASE = '/api/v1'

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const token = localStorage.getItem('token')
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...opts?.headers,
    },
  })
  if (res.status === 401) { localStorage.removeItem('token'); window.location.href = '/login' }
  if (!res.ok) throw new ApiError(res.status, await res.text())
  if (res.status === 204) return undefined as T
  return res.json()
}
```

### 3.3 路由表

```tsx
<Routes>
  <Route path="/login" element={<LoginPage />} />
  <Route path="/admin" element={<AppShell />}>
    <Route index element={<Dashboard />} />
    <Route path="collections" element={<Collections />} />
    <Route path="collections/:id" element={<CollectionDetail />} />
    <Route path="ingestion" element={<Ingestion />} />
    <Route path="ingestion/jobs" element={<IngestionJobs />} />
  </Route>
  <Route path="/chat" element={<ChatLayout />}>
    <Route index element={<ChatView />} />
    <Route path=":sessionId" element={<ChatView />} />
  </Route>
  <Route path="/" element={<Navigate to="/admin" />} />
</Routes>
```

### 3.4 验证

| # | 验证 | 方法 |
|---|------|------|
| 1 | `npm run dev` 无 TS 编译错误 | Vite 启动成功 |
| 2 | `/login` → 登录 → 跳转 `/admin` | 输入凭据 → POST 成功 → redirect |
| 3 | `/admin` → Sidebar 导航切换 | 点击侧边栏 → 路由变化 |
| 4 | `/chat` → 空壳渲染 | 访问 → 无报错 |
| 5 | token 过期 → 自动跳 `/login` | 清 localStorage → 刷新 → redirect |

---

## 4. SP2: Admin UI

**目标**: 知识库 CRUD + 文档管理 + 摄入 + 任务列表全流程可用。

### 4.1 通用数据加载模式

每个页面统一使用 4 态模式：`loading → error → empty → data`

共享组件三件套：
- `LoadingSpinner.tsx` — 居中加载动画
- `ErrorBanner.tsx` — 错误消息 + 重试按钮
- `EmptyState.tsx` — 图标 + 提示文案 + 可选操作按钮

### 4.2 页面清单

#### Dashboard (`/admin`)

```
数据来源:
  useCollections()          → GET /collections
  useIngestionJobs(limit=10) → GET /ingest?limit=10

统计卡片 (3 张):
  知识库总数:  collections.length
  文档总数:    sum(collections[].doc_count)
  任务总数:    jobs.length

最近任务表:
  列: job_id | collection_id | source_type | 进度 | status badge | created_at
```

#### Collections (`/admin/collections`)

```
数据: useCollections() → GET /collections

Table: name | doc_count | chunk_count | status | created_at
操作:
  [新建] → CreateCollectionDialog (name + description) → POST /collections → refetch
  [删除] → ConfirmDialog → DELETE /collections/:id → refetch
  [点击行] → navigate(/admin/collections/:id)
```

#### CollectionDetail (`/admin/collections/:id`)

```
数据:
  useCollection(id) → GET /collections/:id
  useDocuments(id)   → GET /collections/:id/documents

Tab "文档":
  Table: title | source_type | mime_type | file_size | status | ingested_at
  操作: [删除] → DELETE /collections/:id/documents/:did
  空态: "暂无文档，前往摄入页面上传"

Tab "配置":
  <pre>{JSON.stringify(collection.config, null, 2)}</pre>
  空对象 → "未配置"

Tab "搜索测试":
  Input + [搜索] → POST /query { query, collection_ids: [id] }
  → 显示 answer + citations (document_title, text snippet 200字, relevance)
```

#### Ingestion (`/admin/ingestion`)

```
数据: useCollections() → Select options

Tab "本地文件":
  Select 知识库 + <input type="file" multiple>
  [上传并摄入] → FormData(collection_id, files[]) → POST /ingest/local
  → 成功跳转 /admin/ingestion/jobs

Tab "网页":
  Select 知识库 + Textarea(每行一个URL)
  [提交] → POST /ingest/web { collection_id, urls: textarea.split("\n").filter(Boolean) }
  → 成功跳转 /admin/ingestion/jobs

Tab "数据库":
  Select 知识库 + Input db_url + Input query + Input title_column + Input content_columns
  [提交] → POST /ingest/database {
    collection_id, db_url, query, title_column,
    content_columns: input.split(",").map(s => s.trim())
  }
  → 成功跳转 /admin/ingestion/jobs
```

#### IngestionJobs (`/admin/ingestion/jobs`)

```
数据:
  useIngestionJobs({ collection_id }) → GET /ingest?collection_id=X&limit=50
  useCollections() → 筛选下拉

筛选: Select "全部知识库" | 具体 collection → 重新请求
Table: job_id(8位) | collection_id | source_type badge | completed/total | status | created_at
展开行: JSON.stringify(errors, null, 2)
```

### 4.3 文件清单

```
src/routes/admin/
  Dashboard.tsx
  Collections.tsx
  CreateCollectionDialog.tsx
  CollectionDetail.tsx
  Ingestion.tsx
  IngestionJobs.tsx

src/hooks/
  useCollections.ts          # GET /collections → Collection[]
  useCollection.ts           # GET /collections/:id → Collection
  useDocuments.ts            # GET /collections/:id/documents → Document[]
  useIngestionJobs.ts        # GET /ingest?collection_id=&limit= → IngestJob[]

src/components/shared/
  StatsCard.tsx              # icon + value + label
  StatusBadge.tsx            # pending=gray, processing=blue, completed=green, failed=red
  EmptyState.tsx             # icon + title + action button
  ErrorBanner.tsx            # error message + retry
  LoadingSpinner.tsx
  FileDropzone.tsx           # styled <input type="file" multiple

src/api/
  collections.ts             # createCollection, listCollections, getCollection, deleteCollection
  documents.ts               # listDocuments, deleteDocument
  ingestion.ts               # ingestLocal, ingestWeb, ingestDatabase, getJob, listJobs
```

### 4.4 验证

| # | 验证 | 方法 |
|---|------|------|
| 1 | Dashboard 卡片数据准确 | 创建知识库 → 卡片数量更新 |
| 2 | 知识库 CRUD 全流程 | 新建 → 列表 → 删除 → 列表更新 |
| 3 | Detail 3 Tab 独立加载 | 切 Tab 不重请求 |
| 4 | 本地文件 FormData 摄入 | 选文件 → 提交 → 200 → 跳转 |
| 5 | Web/DB 摄入 JSON 提交 | URL/SQL → 提交 → 200 → 跳转 |
| 6 | Jobs 展开 errors | 展开行显示 JSON |
| 7 | 错误状态 + 重试 | 断网 → ErrorBanner → 恢复后重试成功 |

---

## 5. SP3: Chat UI

**目标**: 流式对话 + 引文面板 + 用户反馈 + 会话管理全流程可用。

### 5.1 核心数据流

```
用户发消息
  → 无 sessionId → POST /sessions { collection_id, title: query.slice(0,50) }
  → 有 sessionId → 跳过创建
  → POST /query/stream { query, collection_ids: [selected], session_id }
     ├─ event: status → 更新 StatusBar
     ├─ event: chunk  → 追加 assistant.content
     └─ event: done   → citations, traceId, feedback 按钮出现
  → 消息已由后端持久化 (SP0 修改)
```

### 5.2 SSE 解析 (`src/lib/sse.ts`)

```typescript
// 纯函数，不建 class
async function fetchSSE(
  url: string, body: object,
  onStatus: (data: StatusEvent) => void,
  onChunk: (data: ChunkEvent) => void,
  onDone: (data: DoneEvent) => void,
  signal: AbortSignal,
): Promise<void>
```

- ReadableStream reader + TextDecoder
- 60s AbortController timeout
- 自动拆 event/data 行

### 5.3 页面组件

#### ChatLayout

```
布局:
  Header(知识库Select + [+新会话] + [≡ toggle sidebar])
  + SessionList (w-72, toggleable)
  + <Outlet>

知识库选择器:
  useCollections() → Select options
  默认: session.collection_id 对应的, 否则第一个
  切换: 影响后续 collection_ids, streaming 时 disabled
```

#### ChatView

```
状态管理 (useState):

interface ChatState {
  messages: ChatMessage[]
  statusBar: string | null
  isStreaming: boolean
  selectedCollectionId: string
  activeCitation: Citation | null
  feedbackFormFor: string | null
}

生命周期:
  /chat (无 sessionId):
    欢迎状态 → 用户输入 → POST /sessions → navigate(/chat/:id) → 流式查询

  /chat/:sessionId:
    useSessionHistory(id) 加载历史 → 恢复 messages
    用户输入 → 直接流式查询

消息气泡:
  MessageBubble
    用户: 右对齐, bg-primary
    AI: 左对齐, bg-muted
         streaming: 内容尾追加闪烁光标 ▍
         complete: 显示 citations 编号 + feedback 按钮
```

#### SessionList

```
数据: useSessions() → GET /sessions
排序: last_activity_at DESC
显示: title || "新会话" + 相对时间 + message_count
激活: useParams().sessionId === item.id
删除: 悬停 × → ConfirmDialog → DELETE /sessions/:id
      删除当前 → navigate(/chat)
空态: "暂无历史会话"
```

#### CitationPanel

```
右侧滑出面板 (w-96, overlay, 可关闭):
  每条 Citation:
    文档标题
    文本片段 (截断 200 字符)
    相关度: relevance (0-1)
    chunk_id
点击消息中 [1] → 打开面板, 滚动到对应引文
```

#### FeedbackButtons

```
👍 有用:
  → POST /feedback { trace_id, rating: 5, feedback_type: "helpful" }
  → 按钮 disabled, "已提交 ✓"

👎 不准确:
  → 展开内联表单 (textarea + [提交] [取消])
  → POST /feedback { trace_id, rating: 1, feedback_type: "inaccurate", comment }
  → 表单收起, "已提交 ✓"
```

### 5.4 错误处理

| 场景 | 处理 |
|------|------|
| SSE 60s 超时 | AbortController → "请求超时，请重试" + [重试] |
| 网络中断 | fetch error → "连接中断" + [重试] |
| session 404 | navigate(/chat) + toast "会话不存在" |
| 历史加载失败 | ErrorBanner + 不影响新消息发送 |
| 无知识库 | Select 提示 "请先在 Admin 创建知识库" |

### 5.5 文件清单

```
src/lib/
  sse.ts                       # fetchSSE (ReadableStream + AbortController)

src/routes/chat/
  ChatLayout.tsx               # Header + SessionList + <Outlet>
  ChatView.tsx                 # 消息流 + 输入区 + 引文面板 + 反馈
  SessionList.tsx              # 侧边栏会话列表

src/hooks/
  useSessions.ts               # GET /sessions, DELETE /sessions/:id
  useSessionHistory.ts         # GET /sessions/:id/history
  useChatStream.ts             # create session → fetch SSE → update messages
  useSubmitFeedback.ts         # POST /feedback

src/components/chat/
  MessageBubble.tsx            # 用户/AI 气泡, streaming 光标
  CitationPanel.tsx            # 引文详情面板
  FeedbackButtons.tsx          # 👍👎 + 内联反馈表单
  StatusBar.tsx                # streaming 状态条 (animated)

src/api/
  sessions.ts                  # +listSessions()
  queries.ts                   # +streamQuery()
  feedbacks.ts                 # createFeedback, getFeedback
```

### 5.6 验证

| # | 验证 | 方法 |
|---|------|------|
| 1 | 进入 /chat → 知识库选择 + 欢迎态 | 访问 → 引导文案可见 |
| 2 | 输入问题 → 创建 session → 跳转 | URL 变化 + 侧边栏新项 |
| 3 | chunk 逐字追加 + statusBar 阶段 | 文字渐现 + 状态变化 |
| 4 | done 后 citations + feedback 出现 | 引文编号可见 + 👍👎 可见 |
| 5 | 点击引文 → 面板滑出 | 文档标题+片段+相关度 |
| 6 | 👍 → 按钮 disabled + "已提交" | POST /feedback 成功 |
| 7 | 👎 → 表单 → 提交 → 收起 | feedback_type=inaccurate |
| 8 | 刷新 → 历史消息恢复 | GET history → 消息显示 |
| 9 | 删除当前会话 → 跳转 /chat | navigate + 侧边栏更新 |
| 10 | 切换知识库 → 新 collection_ids | Select 切换 → 验证请求 |
| 11 | 60s 超时 → 提示 + 重试 | AbortController → timeout |
| 12 | 网络中断 → 错误 + 重试 | fetch error → 恢复 |

---

## 6. SP4: 部署

**目标**: Docker Compose 一键启动全栈（Nginx + FastAPI + PostgreSQL + Milvus + Redis）。

### 6.1 文件清单

```
frontend/
├── Dockerfile           # multi-stage: node:22-alpine build → nginx:alpine serve
└── nginx.conf           # SPA fallback + /api/ reverse proxy

根目录:
└── docker-compose.yml   # +frontend service (ports 3000, depends_on fastapi)
```

### 6.2 Dockerfile

```dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
```

### 6.3 Nginx 配置

```nginx
server {
    listen 3000;
    root /usr/share/nginx/html;
    location / {
        try_files $uri /index.html;    # SPA fallback
    }
    location /api/ {
        proxy_pass http://fastapi:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 6.4 数据流

```
开发:  browser → Vite(:5173) → proxy /api → FastAPI(:8000)
生产:  browser → Nginx(:3000) → / → dist/ static files
                               → /api/ → proxy → FastAPI(:8000)
```

### 6.5 验证

| # | 验证 | 方法 |
|---|------|------|
| 1 | `npm run build` 零错误 | cd frontend && npm run build |
| 2 | dist/ 含 index.html + JS chunks | ls dist/ |
| 3 | `docker compose build frontend` 成功 | Docker build |
| 4 | `docker compose up` → :3000 可访问 | 浏览器 |
| 5 | :3000/api/v1/collections → 代理到 FastAPI | curl |
| 6 | 全链路 E2E: Login → Admin 摄入 → Chat 流式 | 手动 |

---

## 7. 全量文件汇总

```
Phase 3 总计: ~55 files

SP0 — 后端补齐:     2 new + 3 mod, ~95 lines
SP1 — 基础设施:     ~18 files
SP2 — Admin UI:     ~16 files
SP3 — Chat UI:      ~16 files
SP4 — 部署:          2 files + 1 mod

按目录:
  app/api/v1/*             5 modified
  app/services/*            1 modified
  frontend/src/api/         7 new
  frontend/src/context/     1 new
  frontend/src/lib/         2 new
  frontend/src/hooks/       8 new
  frontend/src/components/layout/   3 new
  frontend/src/components/ui/       ~10 new (shadcn)
  frontend/src/components/shared/   6 new
  frontend/src/components/chat/     4 new
  frontend/src/routes/admin/        6 new
  frontend/src/routes/chat/         3 new
  frontend/src/routes/LoginPage.tsx 1 new
  frontend/config files             7 new
```

---

## 8. 风险与依赖

| 风险 | 影响 | 缓解 |
|------|------|------|
| SSE 非真流式（agent 阻塞后发 chunk） | 首字节延迟 30-60s | MVP 可接受，真流式改造是 Phase 4 任务 |
| 消息持久化在 SP0 才加入 | 历史功能依赖 SP0 | SP0 先做 |
| shadcn/ui 手动复制可能缺组件 | 样式不完整 | 按需复制，SP1 仅装基础组件 |
| Tailwind CSS 4 与 shadcn 兼容 | 样式问题 | 开发中验证，必要时降级 Tailwind 3 |