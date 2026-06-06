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

      <div className="p-3 border-b" style={{ borderColor: "#e5e7eb" }}>
        {!cols || cols.length === 0 ? (
          <p className="text-xs" style={{ color: "#6b7280" }}>
            Create a collection in Admin first
          </p>
        ) : (
          <select
            className="w-full h-9 rounded-xl px-3 py-1 text-sm"
            style={{
              border: "1px solid #e5e7eb",
              backgroundColor: "#fff",
              color: "#111827",
            }}
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

      <div className="p-2 border-b" style={{ borderColor: "#e5e7eb" }}>
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

      <SessionList onClose={() => setShowSidebar(false)} />

      <div className="p-3 border-t" style={{ borderColor: "#e5e7eb" }}>
        <Link
          to="/admin"
          onClick={() => setShowSidebar(false)}
          className="flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors"
          style={{ color: "#4b5563" }}
        >
          <LayoutDashboard className="h-4 w-4 shrink-0" style={{ color: "#6b7280" }} />
          Admin
        </Link>
      </div>
    </>
  );

  return (
    <div className="flex h-screen">
      <DesktopSidebar>{sidebarContent}</DesktopSidebar>

      <MobileSidebar
        isOpen={showSidebar}
        onClose={() => setShowSidebar(false)}
      >
        {sidebarContent}
      </MobileSidebar>

      <div className="flex-1 flex flex-col min-w-0 md:ml-64">
        <header
          className="md:hidden h-14 flex items-center px-4 shrink-0 border-b"
          style={{ backgroundColor: "#fff", borderColor: "#e5e7eb" }}
        >
          <AnimatedMenuToggle
            toggle={() => setShowSidebar((v) => !v)}
            isOpen={showSidebar}
          />
          <span className="ml-3 font-bold text-lg" style={{ color: "#111827" }}>
            AgentRAG
          </span>
        </header>

        <header
          className="hidden md:flex h-14 border-b items-center px-4 shrink-0"
          style={{ borderColor: "#e5e7eb", color: "#111827" }}
        >
          <span className="font-medium text-sm">Chat</span>
        </header>

        <ChatView selectedCollectionId={selectedColId} />
      </div>
    </div>
  );
}