import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Plus, LayoutDashboard } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SessionList } from "./SessionList";
import { ChatView } from "./ChatView";
import { useCollections } from "@/hooks/useCollections";
import { useAuth } from "@/context/AuthContext";
import {
  ProfileSection,
  DesktopSidebar,
  MobileSidebar,
  AnimatedMenuToggle,
} from "@/components/ui/animated-sidebar";

export function ChatLayout() {
  const [showSidebar, setShowSidebar] = useState(false);
  const { data: cols } = useCollections();
  const [selectedColId, setSelectedColId] = useState("");
  const navigate = useNavigate();
  const { user } = useAuth();

  useEffect(() => {
    if (cols && cols.length > 0 && !selectedColId) {
      setSelectedColId(cols[0].id);
    }
  }, [cols, selectedColId]);

  const sidebarContent = (
    <>
      <ProfileSection username={user?.username ?? "User"} />

      {/* Collection selector */}
      <div className="p-3 border-b shrink-0">
        {(!cols || cols.length === 0) ? (
          <p className="text-xs text-muted-foreground">
            Create a collection in Admin first
          </p>
        ) : (
          <select
            className="w-full h-9 rounded-xl border border-input bg-background px-3 py-1 text-sm"
            value={selectedColId}
            onChange={(e) => setSelectedColId(e.target.value)}
          >
            {cols.map((c: any) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* New session */}
      <div className="p-2 border-b shrink-0">
        <Button
          variant="outline"
          size="sm"
          className="w-full rounded-xl"
          onClick={() => {
            navigate("/chat");
            setShowSidebar(false);
          }}
        >
          <Plus className="h-4 w-4 mr-1" />
          New Session
        </Button>
      </div>

      {/* Session list */}
      <SessionList onClose={() => setShowSidebar(false)} />

      {/* Admin link */}
      <div className="p-3 border-t shrink-0">
        <Link
          to="/admin"
          onClick={() => setShowSidebar(false)}
          className="flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
        >
          <LayoutDashboard className="h-4 w-4 shrink-0" />
          Admin
        </Link>
      </div>
    </>
  );

  return (
    <div className="flex h-screen">
      {/* ── Desktop sidebar ── */}
      <DesktopSidebar>{sidebarContent}</DesktopSidebar>

      {/* ── Mobile overlay ── */}
      <MobileSidebar
        isOpen={showSidebar}
        onClose={() => setShowSidebar(false)}
      >
        {sidebarContent}
      </MobileSidebar>

      {/* ── Main area ── */}
      <div className="flex-1 flex flex-col min-w-0 md:ml-64">
        {/* Mobile header */}
        <header className="md:hidden h-14 border-b flex items-center px-4 shrink-0 bg-background">
          <AnimatedMenuToggle
            toggle={() => setShowSidebar((v) => !v)}
            isOpen={showSidebar}
          />
          <span className="ml-3 font-bold text-lg">AgentRAG</span>
        </header>

        {/* Desktop header */}
        <header className="hidden md:flex h-14 border-b items-center px-4 shrink-0">
          <span className="font-medium text-sm">Chat</span>
        </header>

        <ChatView selectedCollectionId={selectedColId} />
      </div>
    </div>
  );
}