import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Plus, MessageSquare, LayoutDashboard } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SessionList } from "./SessionList";
import { ChatView } from "./ChatView";
import { useCollections } from "@/hooks/useCollections";
import {
  HamburgerToggle,
  ProfileSection,
  MobileSidebarShell,
} from "@/components/ui/animated-sidebar";

export function ChatLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { data: cols } = useCollections();
  const [selectedColId, setSelectedColId] = useState("");
  const navigate = useNavigate();
  const close = () => setMobileOpen(false);

  useEffect(() => {
    if (cols && cols.length > 0 && !selectedColId) {
      setSelectedColId(cols[0].id);
    }
  }, [cols, selectedColId]);

  const SidebarContent = () => (
    <div className="flex flex-col h-full">
      <ProfileSection />

      <div className="p-3 border-y shrink-0">
        {(!cols || cols.length === 0) ? (
          <p className="text-xs text-muted-foreground px-1">
            Create a collection in Admin first
          </p>
        ) : (
          <select
            className="w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm"
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

      <div className="p-2 border-b shrink-0">
        <Button
          variant="outline"
          size="sm"
          className="w-full rounded-xl"
          onClick={() => {
            navigate("/chat");
            close();
          }}
        >
          <Plus className="h-4 w-4 mr-1" />
          New Session
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <SessionList onClose={close} />
      </div>

      <div className="p-3 border-t shrink-0">
        <Link
          to="/admin"
          onClick={close}
          className="flex items-center gap-2 w-full py-2 px-4 rounded-xl text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
        >
          <LayoutDashboard className="h-4 w-4" />
          Admin
        </Link>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen">
      {/* Mobile overlay */}
      <MobileSidebarShell isOpen={mobileOpen} onClose={close}>
        <SidebarContent />
      </MobileSidebarShell>

      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col w-72 bg-background border-r shrink-0">
        <SidebarContent />
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b flex items-center px-4 shrink-0">
          <span className="md:hidden mr-2">
            <HamburgerToggle
              toggle={() => setMobileOpen(!mobileOpen)}
              isOpen={mobileOpen}
            />
          </span>
          <div className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            <span className="font-bold text-lg">AgentRAG</span>
          </div>
        </header>
        <ChatView selectedCollectionId={selectedColId} />
      </div>
    </div>
  );
}