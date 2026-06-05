import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from '@/context/AuthContext'
import { AppShell } from '@/components/layout/AppShell'
import { LoginPage } from '@/routes/LoginPage'

const Dashboard = lazy(() => import('@/routes/admin/Dashboard').then(m => ({ default: m.Dashboard })))
const Collections = lazy(() => import('@/routes/admin/Collections').then(m => ({ default: m.Collections })))
const CollectionDetail = lazy(() => import('@/routes/admin/CollectionDetail').then(m => ({ default: m.CollectionDetail })))
const Ingestion = lazy(() => import('@/routes/admin/Ingestion').then(m => ({ default: m.Ingestion })))
const IngestionJobs = lazy(() => import('@/routes/admin/IngestionJobs').then(m => ({ default: m.IngestionJobs })))
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
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  )
}
