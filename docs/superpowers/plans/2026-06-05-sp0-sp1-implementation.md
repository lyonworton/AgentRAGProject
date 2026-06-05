# SP0 + SP1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete SP0 backend endpoints (+ SP0 modifications) and SP1 frontend scaffolding (Vite + React + Auth + Layout).

**Architecture:** SP0 adds 5 missing API endpoints and 4 modifications to existing endpoints, enabling the frontend. SP1 scaffolds a React 18 + TypeScript + Vite 6 + Tailwind CSS 4 + shadcn/ui (manual copy) frontend with auth, routing, and layout shell.

**Tech Stack:** Python/FastAPI (backend), React 18 + TypeScript + Vite 6 + Tailwind CSS 4 (frontend)

---

## SP0: Backend补齐

### Task 0.1: Run existing tests to get baseline

- [ ] **Step 1: Run all tests**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/ -x -q
```

Expected: all existing tests pass.

---

### Task 0.2: Add `GET /collections/:id` with `config: dict` in response

**Files:**
- Modify: `app/api/v1/collections.py`
- Domain: `Collection` already has `config: Mapped[dict]` column (JSONB) — we just expose it.

- [ ] **Step 1: Update `CollectionResponse` + add `GET /collections/:col_id`**

In `app/api/v1/collections.py`, change `CollectionResponse` from:
```python
class CollectionResponse(BaseModel):
    id: str; name: str; description: str | None; doc_count: int; status: str
    model_config = {"from_attributes": True}
```
To:
```python
class CollectionResponse(BaseModel):
    id: str; name: str; description: str | None; config: dict | None
    doc_count: int; chunk_count: int; status: str
    model_config = {"from_attributes": True}
```

Then insert between `list_collections` and `delete_collection`:
```python
@router.get("/{col_id}", response_model=CollectionResponse)
async def get_collection(col_id: str, db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)):
    col = await collection_service.get_collection(db, col_id)
    if not col or col.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Collection not found")
    return col
```

- [ ] **Step 2: Run tests**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/ -x -q
```

- [ ] **Step 3: Commit**

```bash
git add app/api/v1/collections.py
git commit -m "feat(sp0): add GET /collections/:id + config field in CollectionResponse"
```

---

### Task 0.3: Add `GET /ingest` list endpoint

**Files:**
- Modify: `app/api/v1/ingestion.py`
- Domain: `IngestJob` fields — id, collection_id, user_id, source_type, total_docs, completed_docs, failed_docs, errors, status, started_at, completed_at, created_at

- [ ] **Step 1: Add `IngestJobListItem` + `GET /ingest`**

Add to `app/api/v1/ingestion.py`, before the existing `IngestJobResponse` and `GET /{job_id}`:

```python
from sqlalchemy import select as sa_select


class IngestJobListItem(BaseModel):
    id: str; collection_id: str; source_type: str; status: str
    total_docs: int; completed_docs: int; failed_docs: int
    errors: list; started_at: str | None; completed_at: str | None; created_at: str | None
    model_config = {"from_attributes": True}


@router.get("", response_model=list[IngestJobListItem])
async def list_ingest_jobs(
    collection_id: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = sa_select(IngestJob).where(IngestJob.user_id == user.id)
    if collection_id:
        q = q.where(IngestJob.collection_id == collection_id)
    q = q.order_by(IngestJob.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()
```

The `sa_select` alias avoids conflict with the existing `from sqlalchemy import select` import in the sessions module (not here, but safe pattern). Actually, this file doesn't import select yet, so just use `from sqlalchemy import select`.

- [ ] **Step 2: Run tests**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/ -x -q
```

- [ ] **Step 3: Commit**

```bash
git add app/api/v1/ingestion.py
git commit -m "feat(sp0): add GET /ingest list endpoint with collection_id filter"
```

---

### Task 0.4: Add `POST /ingest/web` + `POST /ingest/database` endpoints

**Files:**
- Modify: `app/api/v1/ingestion.py`
- Worker: `app/workers/ingest.py` already has `start_ingest_job` with "web" and "database" support.

- [ ] **Step 1: Add request models + both POST endpoints**

Add to `app/api/v1/ingestion.py` (right after the `POST /local` block, before `IngestJobResponse`):

```python
class WebIngestRequest(BaseModel):
    collection_id: str
    urls: list[str]


class DatabaseIngestRequest(BaseModel):
    collection_id: str
    db_url: str
    query: str
    title_column: str
    content_columns: list[str]


@router.post("/web")
async def ingest_web(req: WebIngestRequest, db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)):
    col = await collection_service.get_collection(db, req.collection_id)
    if not col or col.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Collection not found")
    job = IngestJob(collection_id=req.collection_id, user_id=user.id, source_type="web",
                    config_snapshot={"urls": req.urls})
    db.add(job); await db.commit(); await db.refresh(job)
    arq_job_id = await enqueue_ingest(
        str(job.id), req.collection_id, user.id,
        source_type="web", source_config={"urls": req.urls},
    )
    return {"job_id": job.id, "arq_job_id": arq_job_id}


@router.post("/database")
async def ingest_database(req: DatabaseIngestRequest, db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)):
    col = await collection_service.get_collection(db, req.collection_id)
    if not col or col.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Collection not found")
    job = IngestJob(collection_id=req.collection_id, user_id=user.id, source_type="database",
                    config_snapshot={"db_url": req.db_url, "query": req.query,
                                     "title_column": req.title_column,
                                     "content_columns": req.content_columns})
    db.add(job); await db.commit(); await db.refresh(job)
    arq_job_id = await enqueue_ingest(
        str(job.id), req.collection_id, user.id,
        source_type="database",
        source_config={
            "db_url": req.db_url, "query": req.query,
            "title_column": req.title_column,
            "content_columns": req.content_columns,
        },
    )
    return {"job_id": job.id, "arq_job_id": arq_job_id}
```

- [ ] **Step 2: Run tests**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/ -x -q
```

- [ ] **Step 3: Commit**

```bash
git add app/api/v1/ingestion.py
git commit -m "feat(sp0): add POST /ingest/web + POST /ingest/database endpoints"
```

---

### Task 0.5: Add `list_sessions` service + `GET /sessions` endpoint

**Files:**
- Modify: `app/services/session_service.py` — add `list_sessions()`
- Modify: `app/api/v1/sessions.py` — add `GET /sessions` endpoint, reorder routes so `GET ""` comes before `GET "/{session_id}"`

- [ ] **Step 1: Add `list_sessions` to `app/services/session_service.py`**

Insert before the `update_session_context` function at the bottom:
```python
async def list_sessions(db: AsyncSession, user_id: str, limit: int = 50) -> list[Session]:
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user_id, Session.is_active == True)
        .order_by(Session.last_activity_at.desc().nullslast())
        .limit(limit)
    )
    return list(result.scalars().all())
```

- [ ] **Step 2: Add `GET /sessions` + reorder routes in `app/api/v1/sessions.py`**

Current route order in `sessions.py`:
1. `POST ""` — create (line 46)
2. `GET "/{session_id}"` — get single (line 55)
3. `DELETE "/{session_id}"` — delete (line 67)
4. `GET "/{session_id}/history"` — history (line 78)

Must insert `GET ""` between (1) and (2), so:
1. `POST ""` — create
2. **`GET ""` — list (NEW)**
3. `GET "/{session_id}"` — get single
4. `DELETE "/{session_id}"` — delete
5. `GET "/{session_id}/history"` — history

Insert after the `create_session` endpoint:
```python
@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await session_service.list_sessions(db, user.id)
```

- [ ] **Step 3: Run tests**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/ -x -q
```

- [ ] **Step 4: Commit**

```bash
git add app/services/session_service.py app/api/v1/sessions.py
git commit -m "feat(sp0): add list_sessions service + GET /sessions endpoint"
```

---

### Task 0.6: Add `citations` to `done` SSE event + `add_message()` persistence after query

**Files:**
- Modify: `app/api/v1/queries.py`

- [ ] **Step 1: Import `session_service`**

Add at the top of `queries.py`:
```python
from app.services import session_service
```

- [ ] **Step 2: Update `query_stream` event_stream to include citations + persistence**

Replace the inner `event_stream()` function body with:

```python
async def event_stream():
    import json
    rag = get_rag_service()
    opts = req.options.model_dump() if req.options else {}
    yield f"event: status\ndata: {json.dumps({'phase': 'analyzing', 'message': 'Understanding query...'})}\n\n"
    result = await rag.query(db, user.id, req.query, req.collection_ids, req.session_id, opts)
    trace_id = uuid.uuid4().hex[:16]
    chunks = result["answer"].split(" ")
    for i in range(0, len(chunks), 5):
        text = " ".join(chunks[i:i+5])
        yield f"event: chunk\ndata: {json.dumps({'text': text + ' ', 'citations': []})}\n\n"
    yield f"event: done\ndata: {json.dumps({'trace_id': trace_id, 'citations': result['citations'], 'iterations': result['agent_trace']['iterations'], 'quality_score': result['agent_trace']['quality_score']})}\n\n"
    if req.session_id:
        await session_service.add_message(db, req.session_id, role="user", content=req.query)
        await session_service.add_message(
            db, req.session_id, role="assistant", content=result["answer"],
            trace_id=trace_id, citations=result.get("citations"),
        )
```

- [ ] **Step 3: Run tests**

```bash
cd D:\artificialintelligent\AgentRAGProject && python -m pytest tests/ -x -q
```

- [ ] **Step 4: Commit**

```bash
git add app/api/v1/queries.py
git commit -m "feat(sp0): done SSE includes citations + message persistence after query"
```

---

## SP1: Frontend Infrastructure

### Task 1.1: Scaffold Vite + React + TypeScript project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/vite-env.d.ts`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "agentrag-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite --port 3000",
    "build": "tsc -b && vite build",
    "preview": "vite preview --port 3000"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0",
    "lucide-react": "^0.460.0",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.6.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "~5.6.0",
    "vite": "^6.0.0",
    "tailwindcss": "^4.0.0",
    "@tailwindcss/vite": "^4.0.0"
  }
}
```

- [ ] **Step 2: Create `frontend/vite.config.ts`**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 3: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true,
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Create `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AgentRAG</title>
  </head>
  <body class="antialiased">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create `frontend/src/vite-env.d.ts`**

```typescript
/// <reference types="vite/client" />
```

- [ ] **Step 6: Install dependencies**

```bash
cd D:\artificialintelligent\AgentRAGProject\frontend && npm install
```

Expected: npm install completes without errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/vite.config.ts frontend/tsconfig.json frontend/index.html frontend/src/vite-env.d.ts
git commit -m "feat(sp1): scaffold Vite + React + TypeScript project"
```

---

### Task 1.2: Set up Tailwind CSS + shadcn/ui CSS variables + utils

**Files:**
- Create: `frontend/src/index.css`
- Create: `frontend/src/lib/utils.ts`

- [ ] **Step 1: Create `frontend/src/index.css`**

```css
@import "tailwindcss";

@theme {
  --color-background: hsl(0 0% 100%);
  --color-foreground: hsl(222.2 84% 4.9%);
  --color-card: hsl(0 0% 100%);
  --color-card-foreground: hsl(222.2 84% 4.9%);
  --color-popover: hsl(0 0% 100%);
  --color-popover-foreground: hsl(222.2 84% 4.9%);
  --color-primary: hsl(222.2 47.4% 11.2%);
  --color-primary-foreground: hsl(210 40% 98%);
  --color-secondary: hsl(210 40% 96.1%);
  --color-secondary-foreground: hsl(222.2 47.4% 11.2%);
  --color-muted: hsl(210 40% 96.1%);
  --color-muted-foreground: hsl(215.4 16.3% 46.9%);
  --color-accent: hsl(210 40% 96.1%);
  --color-accent-foreground: hsl(222.2 47.4% 11.2%);
  --color-destructive: hsl(0 84.2% 60.2%);
  --color-destructive-foreground: hsl(210 40% 98%);
  --color-border: hsl(214.3 31.8% 91.4%);
  --color-input: hsl(214.3 31.8% 91.4%);
  --color-ring: hsl(222.2 84% 4.9%);
  --radius: 0.5rem;
}
```

- [ ] **Step 2: Create `frontend/src/lib/utils.ts`**

```typescript
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/index.css frontend/src/lib/utils.ts
git commit -m "feat(sp1): add Tailwind CSS 4 + shadcn CSS variables + cn utility"
```

---

### Task 1.3: Create shadcn/ui base components (Button, Input, Card, Label)

**Files:**
- Create: `frontend/src/components/ui/button.tsx`
- Create: `frontend/src/components/ui/input.tsx`
- Create: `frontend/src/components/ui/card.tsx`
- Create: `frontend/src/components/ui/label.tsx`

- [ ] **Step 1: Create `frontend/src/components/ui/button.tsx`**

```typescript
import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
  )
)
Button.displayName = "Button"
export { Button, buttonVariants }
```

- [ ] **Step 2: Create `frontend/src/components/ui/input.tsx`**

```typescript
import * as React from "react"
import { cn } from "@/lib/utils"

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      className={cn(
        "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      ref={ref}
      {...props}
    />
  )
)
Input.displayName = "Input"
export { Input }
```

- [ ] **Step 3: Create `frontend/src/components/ui/card.tsx`**

```typescript
import * as React from "react"
import { cn } from "@/lib/utils"

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("rounded-lg border bg-card text-card-foreground shadow-sm", className)} {...props} />
  )
)
Card.displayName = "Card"

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-col space-y-1.5 p-6", className)} {...props} />
  )
)
CardHeader.displayName = "CardHeader"

const CardTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn("text-2xl font-semibold leading-none tracking-tight", className)} {...props} />
  )
)
CardTitle.displayName = "CardTitle"

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
  )
)
CardContent.displayName = "CardContent"

export { Card, CardHeader, CardTitle, CardContent }
```

- [ ] **Step 4: Create `frontend/src/components/ui/label.tsx`**

```typescript
import * as React from "react"
import { cn } from "@/lib/utils"

const Label = React.forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      className={cn("text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70", className)}
      {...props}
    />
  )
)
Label.displayName = "Label"
export { Label }
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/
git commit -m "feat(sp1): add shadcn/ui base components (Button, Input, Card, Label)"
```

---

### Task 1.4: Create API client + Auth API

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/auth.ts`

- [ ] **Step 1: Create `frontend/src/api/client.ts`**

```typescript
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

const BASE = '/api/v1'

export async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const token = localStorage.getItem('token')
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...opts?.headers,
    },
  })
  if (res.status === 401) {
    localStorage.removeItem('token')
    window.location.href = '/login'
    throw new ApiError(401, 'Unauthorized')
  }
  if (!res.ok) {
    const body = await res.text()
    throw new ApiError(res.status, body || res.statusText)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}
```

- [ ] **Step 2: Create `frontend/src/api/auth.ts`**

```typescript
import { request } from './client'

interface LoginResponse {
  access_token: string
  token_type: string
  user: { id: string; username: string }
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const data = await request<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  localStorage.setItem('token', data.access_token)
  return data
}

interface RegisterResponse {
  id: string
  username: string
}

export async function register(username: string, password: string): Promise<RegisterResponse> {
  return request<RegisterResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/
git commit -m "feat(sp1): add API client (fetch wrapper) + auth API calls"
```

---

### Task 1.5: Create AuthContext

**Files:**
- Create: `frontend/src/context/AuthContext.tsx`

- [ ] **Step 1: Create `frontend/src/context/AuthContext.tsx`**

```typescript
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { login as apiLogin } from '@/api/auth'

interface User {
  id: string
  username: string
}

interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'))
  const [user, setUser] = useState<User | null>(null)

  const login = useCallback(async (username: string, password: string) => {
    const data = await apiLogin(username, password)
    setToken(data.access_token)
    setUser(data.user)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ token, user, isAuthenticated: !!token, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/context/AuthContext.tsx
git commit -m "feat(sp1): add AuthContext with login/logout + token persistence"
```

---

### Task 1.6: Create Layout components (Sidebar + Header + AppShell)

**Files:**
- Create: `frontend/src/components/layout/Sidebar.tsx`
- Create: `frontend/src/components/layout/Header.tsx`
- Create: `frontend/src/components/layout/AppShell.tsx`

- [ ] **Step 1: Create `frontend/src/components/layout/Sidebar.tsx`**

```typescript
import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Database, Upload, ListTodo } from 'lucide-react'
import { cn } from '@/lib/utils'

const items = [
  { to: '/admin', icon: LayoutDashboard, label: '仪表盘', end: true },
  { to: '/admin/collections', icon: Database, label: '知识库' },
  { to: '/admin/ingestion', icon: Upload, label: '摄入' },
  { to: '/admin/ingestion/jobs', icon: ListTodo, label: '任务' },
]

export function Sidebar() {
  return (
    <aside className="w-56 border-r bg-muted/40 flex flex-col shrink-0">
      <div className="h-14 flex items-center px-4 border-b font-bold text-lg">
        AgentRAG
      </div>
      <nav className="flex-1 p-2 space-y-1">
        {items.map(({ to, icon: Icon, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
```

- [ ] **Step 2: Create `frontend/src/components/layout/Header.tsx`**

```typescript
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { LogOut } from 'lucide-react'

export function Header() {
  const { user, logout } = useAuth()

  return (
    <header className="h-14 border-b flex items-center justify-between px-6 shrink-0">
      <span className="text-sm text-muted-foreground">欢迎回来</span>
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium">{user?.username ?? '未登录'}</span>
        <Button variant="ghost" size="sm" onClick={logout}>
          <LogOut className="h-4 w-4 mr-1" /> 登出
        </Button>
      </div>
    </header>
  )
}
```

- [ ] **Step 3: Create `frontend/src/components/layout/AppShell.tsx`**

```typescript
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'

export function AppShell() {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/layout/
git commit -m "feat(sp1): add AppShell layout (Sidebar + Header + Outlet)"
```

---

### Task 1.7: Create LoginPage

**Files:**
- Create: `frontend/src/routes/LoginPage.tsx`

- [ ] **Step 1: Create `frontend/src/routes/LoginPage.tsx`**

```typescript
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/admin')
    } catch (err: any) {
      setError(err?.message || '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/40">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>登录 AgentRAG</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">用户名</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">密码</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? '登录中...' : '登录'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/routes/LoginPage.tsx
git commit -m "feat(sp1): add LoginPage with username/password form"
```

---

### Task 1.8: Create App.tsx + main.tsx with routing

**Files:**
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/routes/admin/Dashboard.tsx` (placeholder)
- Create: `frontend/src/routes/admin/Collections.tsx` (placeholder)
- Create: `frontend/src/routes/chat/ChatLayout.tsx` (placeholder)
- Create: `frontend/src/routes/chat/ChatView.tsx` (placeholder)

- [ ] **Step 1: Create placeholder pages**

Create `frontend/src/routes/admin/Dashboard.tsx`:
```typescript
export function Dashboard() {
  return (
    <div className="flex items-center justify-center h-full">
      <p className="text-muted-foreground text-lg">仪表盘 — 即将在 SP2 实现</p>
    </div>
  )
}
```

Create `frontend/src/routes/admin/Collections.tsx`:
```typescript
export function Collections() {
  return (
    <div className="flex items-center justify-center h-full">
      <p className="text-muted-foreground text-lg">知识库 — 即将在 SP2 实现</p>
    </div>
  )
}
```

Create `frontend/src/routes/chat/ChatLayout.tsx`:
```typescript
import { Outlet } from 'react-router-dom'

export function ChatLayout() {
  return (
    <div className="flex h-screen">
      <main className="flex-1 flex flex-col">
        <Outlet />
      </main>
    </div>
  )
}
```

Create `frontend/src/routes/chat/ChatView.tsx`:
```typescript
export function ChatView() {
  return (
    <div className="flex items-center justify-center h-full">
      <p className="text-muted-foreground text-lg">对话 — 即将在 SP3 实现</p>
    </div>
  )
}
```

- [ ] **Step 2: Create `frontend/src/App.tsx`**

```typescript
import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from '@/context/AuthContext'
import { AppShell } from '@/components/layout/AppShell'
import { LoginPage } from '@/routes/LoginPage'

const Dashboard = lazy(() => import('@/routes/admin/Dashboard').then(m => ({ default: m.Dashboard })))
const Collections = lazy(() => import('@/routes/admin/Collections').then(m => ({ default: m.Collections })))
const ChatLayout = lazy(() => import('@/routes/chat/ChatLayout').then(m => ({ default: m.ChatLayout })))
const ChatView = lazy(() => import('@/routes/chat/ChatView').then(m => ({ default: m.ChatView })))

function Loading() {
  return <div className="flex items-center justify-center h-screen text-muted-foreground">加载中...</div>
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/admin" element={<AppShell />}>
              <Route index element={<Dashboard />} />
              <Route path="collections" element={<Collections />} />
            </Route>
            <Route path="/chat" element={<ChatLayout />}>
              <Route index element={<ChatView />} />
              <Route path=":sessionId" element={<ChatView />} />
            </Route>
            <Route path="/" element={<Navigate to="/admin" />} />
          </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  )
}
```

- [ ] **Step 3: Create `frontend/src/main.tsx`**

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/main.tsx frontend/src/App.tsx frontend/src/routes/
git commit -m "feat(sp1): add App.tsx with routing + placeholder pages + main.tsx"
```

---

### Task 1.9: SP1 build verification

- [ ] **Step 1: Start the dev server**

```bash
cd D:\artificialintelligent\AgentRAGProject\frontend && npm run dev
```

Expected: Vite dev server starts on http://localhost:3000 with no TypeScript or build errors.

- [ ] **Step 2: Verify TypeScript compilation**

```bash
cd D:\artificialintelligent\AgentRAGProject\frontend && npx tsc --noEmit
```

Expected: No TypeScript errors.

---

## Verification Checklist

SP0:
- [ ] `pytest tests/ -x -q` all pass
- [ ] `GET /api/v1/collections/:id` returns Collection with `config` field
- [ ] `GET /api/v1/ingest` lists ingest jobs
- [ ] `POST /api/v1/ingest/web` enqueues web ingestion
- [ ] `POST /api/v1/ingest/database` enqueues DB ingestion
- [ ] `GET /api/v1/sessions` lists sessions
- [ ] SSE `done` event includes `citations`
- [ ] Messages persisted after stream query

SP1:
- [ ] `npm run dev` starts without TS errors on :3000
- [ ] `/login` → login form visible → submit → redirect to `/admin`
- [ ] `/admin` → Sidebar navigation switches routes
- [ ] `/chat` → renders placeholder
- [ ] `npx tsc --noEmit` zero errors