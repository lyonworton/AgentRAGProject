import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { LogOut } from "lucide-react";
import { HamburgerToggle } from "@/components/ui/animated-sidebar";

interface HeaderProps {
  mobileOpen: boolean;
  onToggleMobile: () => void;
}

export function Header({ mobileOpen, onToggleMobile }: HeaderProps) {
  const { user, logout } = useAuth();

  return (
    <header className="h-14 border-b flex items-center justify-between px-4 shrink-0">
      <div className="flex items-center gap-3">
        <span className="md:hidden">
          <HamburgerToggle toggle={onToggleMobile} isOpen={mobileOpen} />
        </span>
        <span className="text-sm text-muted-foreground">
          {user?.username ?? "User"}
        </span>
      </div>
      <Button variant="ghost" size="sm" onClick={logout}>
        <LogOut className="h-4 w-4 mr-1" />
        Logout
      </Button>
    </header>
  );
}