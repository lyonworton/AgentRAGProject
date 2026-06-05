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
