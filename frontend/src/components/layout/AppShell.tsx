import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const toggle = () => setMobileOpen(!mobileOpen);

  return (
    <div className="flex h-screen">
      <Sidebar mobileOpen={mobileOpen} onToggleMobile={toggle} />
      <div className="flex-1 flex flex-col min-h-0 min-w-0 md:ml-64 transition-all duration-300">
        <Header mobileOpen={mobileOpen} onToggleMobile={toggle} />
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}