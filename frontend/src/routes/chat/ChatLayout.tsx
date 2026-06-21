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
import { cn } from "@/lib/utils";

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

      {/* Collection selector */}
      <div className="px-3 py-2.5 border-b border-border/30">
        {(!cols || cols.length === 0) ? (
          <p className="text-xs text-muted-foreground/60 px-1 font-medium">
            Create a collection in Admin first
          </p>
        ) : (
          <select
            className="w-full h-8 rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-semibold text-muted-foreground/70 focus:outline-none focus:ring-2 focus:ring-primary/15 focus:ring-offset-1 disabled:cursor-not-allowed appearance-none cursor-pointer transition-all duration-150"
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

      {/* New session button */}
      <div className="p-2.5">
        <Button
          variant="outline"
          size="sm"
          className="w-full rounded-lg"
          onClick={() => {
            navigate("/chat");
            close();
          }}
        >
          <Plus className="h-3.5 w-3.5 mr-1.5" strokeWidth={2} />
          New Session
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <SessionList onClose={close} />
      </div>

      {/* Admin link */}
      <div className="p-3 border-t border-border/30">
        <Link
          to="/admin"
          onClick={close}
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-muted-foreground/60 hover:bg-accent/40 hover:text-foreground transition-colors duration-150"
        >
          <LayoutDashboard className="h-3.5 w-3.5" strokeWidth={1.8} />
          Admin Panel
        </Link>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-background">
      {/* Mobile overlay */}
      <MobileSidebarShell isOpen={mobileOpen} onClose={close}>
        <SidebarContent />
      </MobileSidebarShell>

      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col w-72 bg-card border-r border-border/50 shrink-0">
        <SidebarContent />
      </aside>

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className={cn(
          "h-14 border-b flex items-center px-4 shrink-0",
          "md:hidden border-border/40 bg-card/80 backdrop-blur-sm"
        )}>
          <span className="md:hidden mr-2">
            <HamburgerToggle
              toggle={() => setMobileOpen(!mobileOpen)}
              isOpen={mobileOpen}
            />
          </span>
          <div className="flex items-center gap-2.5">
            <MessageSquare className="h-5 w-5 text-primary/50" strokeWidth={1.8} />
            <span className="font-semibold text-sm tracking-tight text-foreground/80">
              AgentRAG
            </span>
          </div>
        </header>
        <ChatView selectedCollectionId={selectedColId} />
      </div>
    </div>
  );
}
