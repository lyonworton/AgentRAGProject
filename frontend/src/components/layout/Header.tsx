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
        <span className="text-sm text-muted-foreground/70 font-medium">
          {user?.username ?? 'User'}
        </span>
      </div>
      <Button variant="ghost" size="sm" onClick={logout} className="h-8 px-3 text-xs">
        <LogOut className="h-3.5 w-3.5 mr-1.5" />
        Logout
      </Button>
    </header>
  )
}
