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
