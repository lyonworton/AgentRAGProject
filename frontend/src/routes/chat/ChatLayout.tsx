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
