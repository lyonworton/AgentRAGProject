import { LogOut } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/context/AuthContext'
import { HamburgerToggle } from '@/components/ui/animated-sidebar'

interface HeaderProps {
  mobileOpen: boolean
  onToggleMobile: () => void
}

export function Header({ mobileOpen, onToggleMobile }: HeaderProps) {
  const { user, logout } = useAuth()

  return (
    <header className="h-14 border-b border-border/40 flex items-center justify-between px-5 shrink-0 bg-card/80 backdrop-blur-sm">
      <div className="flex items-center gap-3">
        <span className="md:hidden">
          <HamburgerToggle toggle={onToggleMobile} isOpen={mobileOpen} />
        </span>
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded-md bg-primary/10 flex items-center justify-center">
            <div className="w-2.5 h-2.5 rounded-sm bg-primary/50" />
          </div>
          <span className="text-sm font-semibold tracking-tight text-foreground/80">
            AgentRAG
          </span>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className="hidden sm:block text-xs font-medium text-muted-foreground/60">
          {user?.username ?? 'User'}
        </span>
        <Button variant="ghost" size="sm" onClick={logout} className="h-8 px-2.5 text-xs rounded-lg">
          <LogOut className="h-3.5 w-3.5 mr-1.5" />
          Logout
        </Button>
      </div>
    </header>
  )
}
