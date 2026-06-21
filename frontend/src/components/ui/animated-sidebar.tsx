import { useState, type ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { User, ChevronDown, ChevronUp } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { cn } from "@/lib/utils";

/* ── HamburgerToggle ── */
export function HamburgerToggle({
  toggle,
  isOpen,
}: {
  toggle: () => void;
  isOpen: boolean;
}) {
  return (
    <button
      onClick={toggle}
      aria-label="Toggle menu"
      className="focus:outline-none z-50 p-1 rounded-md hover:bg-muted transition-colors"
    >
      <motion.div
        animate={{ rotate: isOpen ? 90 : 0 }}
        transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <motion.line x1="3" y1="6" x2="21" y2="6" />
          <motion.line x1="3" y1="12" x2="21" y2="12" />
          <motion.line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </motion.div>
    </button>
  );
}

/* ── CollapsibleSection ── */
export function CollapsibleSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mb-0.5">
      <button
        className={cn(
          "w-full flex items-center justify-between py-1.5 px-3 rounded-md text-xs font-semibold uppercase tracking-wider transition-colors duration-150",
          "text-muted-foreground/60 hover:text-muted-foreground hover:bg-muted/50",
          open && "text-foreground/80 bg-muted/60"
        )}
        onClick={() => setOpen(!open)}
      >
        <span>{title}</span>
        {open ? (
          <ChevronUp className="h-3.5 w-3.5" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5" />
        )}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="pl-4 py-0.5">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── ProfileSection ── */
export function ProfileSection() {
  const { user } = useAuth();

  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-border/40">
      <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center shrink-0">
        <User className="h-4 w-4 text-primary/70" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-sm leading-tight truncate text-foreground/90">
          {user?.username ?? "User"}
        </p>
        <p className="text-[11px] text-muted-foreground/50 truncate mt-0.5">
          {user?.id?.slice(0, 8) ?? "—"}
        </p>
      </div>
    </div>
  );
}

/* ── MobileSidebarShell ── */
const mobileSidebarVariants = {
  hidden: { x: "-100%" },
  visible: { x: 0 },
};

export function MobileSidebarShell({
  isOpen,
  onClose,
  children,
}: {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            className="fixed inset-0 bg-black/40 z-40 md:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
          />
          <motion.div
            initial="hidden"
            animate="visible"
            exit="hidden"
            variants={mobileSidebarVariants}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="fixed inset-y-0 left-0 z-50 w-72 bg-card border-r border-border/60 flex flex-col md:hidden shadow-elevated"
          >
            {children}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
