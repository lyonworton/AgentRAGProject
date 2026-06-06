import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Database,
  Upload,
  ListTodo,
  MessageSquare,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import {
  ProfileSection,
  DesktopSidebar,
  MobileSidebar,
  AnimatedMenuToggle,
} from "@/components/ui/animated-sidebar";

const items = [
  { to: "/admin", icon: LayoutDashboard, label: "Dashboard", end: true },
  { to: "/admin/collections", icon: Database, label: "Collections" },
  { to: "/admin/ingestion", icon: Upload, label: "Ingestion" },
  { to: "/admin/ingestion/jobs", icon: ListTodo, label: "Jobs" },
  { to: "/chat", icon: MessageSquare, label: "Chat" },
];

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav
      className="flex-1 p-3 space-y-1 overflow-y-auto"
      style={{ color: "#4b5563" }}
    >
      {items.map(({ to, icon: Icon, label, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors"
          style={({ isActive }) =>
            isActive
              ? { backgroundColor: "#eff6ff", color: "#2563eb" }
              : { color: "#4b5563" }
          }
        >
          {({ isActive }) => (
            <>
              <Icon className="h-4 w-4 shrink-0" style={{ color: isActive ? "#2563eb" : "#6b7280" }} />
              {label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

export function Sidebar() {
  const { user } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const sidebarContent = (
    <>
      <ProfileSection username={user?.username ?? "User"} />
      <NavItems onNavigate={() => setMobileOpen(false)} />
    </>
  );

  return (
    <>
      <DesktopSidebar>{sidebarContent}</DesktopSidebar>

      <div
        className="md:hidden fixed top-0 left-0 right-0 z-30 h-14 flex items-center px-4 border-b"
        style={{ backgroundColor: "#fff", borderColor: "#e5e7eb", color: "#111827" }}
      >
        <AnimatedMenuToggle
          toggle={() => setMobileOpen((v) => !v)}
          isOpen={mobileOpen}
        />
        <span className="ml-3 font-bold text-lg">AgentRAG</span>
      </div>

      <MobileSidebar isOpen={mobileOpen} onClose={() => setMobileOpen(false)}>
        {sidebarContent}
      </MobileSidebar>
    </>
  );
}