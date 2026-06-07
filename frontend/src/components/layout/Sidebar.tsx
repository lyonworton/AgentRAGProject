import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Database,
  Upload,
  ListTodo,
  MessageSquare,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  ProfileSection,
  CollapsibleSection,
  MobileSidebarShell,
} from "@/components/ui/animated-sidebar";

const navItems = [
  { to: "/admin", icon: LayoutDashboard, label: "Dashboard", end: true },
  { to: "/admin/collections", icon: Database, label: "Collections" },
];

interface SidebarProps {
  mobileOpen: boolean;
  onToggleMobile: () => void;
}

export function Sidebar({ mobileOpen, onToggleMobile }: SidebarProps) {
  const close = () => onToggleMobile();

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      "flex items-center gap-3 px-4 py-2 rounded-xl text-sm font-medium transition-colors",
      isActive
        ? "bg-primary text-primary-foreground"
        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
    );

  const NavLinks = () => (
    <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
      {navItems.map(({ to, icon: Icon, label, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={linkClass}
          onClick={close}
        >
          <Icon className="h-4 w-4" />
          {label}
        </NavLink>
      ))}

      <CollapsibleSection title="Ingestion">
        <NavLink to="/admin/ingestion" className={linkClass} onClick={close}>
          <Upload className="h-4 w-4" />
          Ingestion
        </NavLink>
        <NavLink to="/admin/ingestion/jobs" className={linkClass} onClick={close}>
          <ListTodo className="h-4 w-4" />
          Jobs
        </NavLink>
      </CollapsibleSection>

      <NavLink to="/chat" className={linkClass} onClick={close}>
        <MessageSquare className="h-4 w-4" />
        Chat
      </NavLink>
    </nav>
  );

  return (
    <>
      <MobileSidebarShell isOpen={mobileOpen} onClose={close}>
        <ProfileSection />
        <NavLinks />
      </MobileSidebarShell>

      <aside className="hidden md:flex flex-col fixed top-0 left-0 h-full w-64 bg-background border-r">
        <ProfileSection />
        <NavLinks />
      </aside>
    </>
  );
}