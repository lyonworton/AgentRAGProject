import { useState, type ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { User } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

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
      className="focus:outline-none z-50"
    >
      <motion.div
        animate={{ y: isOpen ? 13 : 0 }}
        transition={{ duration: 0.3 }}
      >
        <motion.svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          initial="closed"
          animate={isOpen ? "open" : "closed"}
          transition={{ duration: 0.3 }}
          className="text-foreground"
        >
          <motion.path
            fill="transparent"
            strokeWidth="2"
            stroke="currentColor"
            strokeLinecap="round"
            variants={{
              closed: { d: "M 2 2.5 L 22 2.5" },
              open: { d: "M 3 16.5 L 17 2.5" },
            }}
          />
          <motion.path
            fill="transparent"
            strokeWidth="2"
            stroke="currentColor"
            strokeLinecap="round"
            variants={{
              closed: { d: "M 2 12 L 22 12", opacity: 1 },
              open: { opacity: 0 },
            }}
            transition={{ duration: 0.2 }}
          />
          <motion.path
            fill="transparent"
            strokeWidth="2"
            stroke="currentColor"
            strokeLinecap="round"
            variants={{
              closed: { d: "M 2 21.5 L 22 21.5" },
              open: { d: "M 3 2.5 L 17 16.5" },
            }}
          />
        </motion.svg>
      </motion.div>
    </button>
  );
}

/* ── CollapsibleSection ── */
const ChevronDown = () => (
  <motion.svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <motion.polyline points="6 9 12 15 18 9" />
  </motion.svg>
);

const ChevronUp = () => (
  <motion.svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <motion.polyline points="18 15 12 9 6 15" />
  </motion.svg>
);

export function CollapsibleSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mb-1">
      <button
        className="w-full flex items-center justify-between py-1.5 px-3 rounded-md hover:bg-accent/60 transition-colors text-xs font-semibold uppercase tracking-wider text-muted-foreground/70"
        onClick={() => setOpen(!open)}
      >
        <span>{title}</span>
        {open ? <ChevronUp /> : <ChevronDown />}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
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
    <div className="flex items-center gap-3 px-4 py-3.5 border-b border-border/30">
      <div className="w-9 h-9 bg-primary/8 rounded-full flex items-center justify-center shrink-0">
        <User className="h-4.5 w-4.5 text-primary-foreground/80" />
      </div>
      <div className="min-w-0">
        <p className="font-semibold text-sm leading-tight truncate text-foreground">
          {user?.username ?? "User"}
        </p>
        <p className="text-[11px] text-muted-foreground/60 truncate">
          {user?.id?.slice(0, 8) ?? '—'}
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
            className="md:hidden fixed inset-0 bg-black/30 z-40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            initial="hidden"
            animate="visible"
            exit="hidden"
            variants={mobileSidebarVariants}
            transition={{ duration: 0.3 }}
            className="fixed inset-y-0 left-0 z-50 w-64 bg-card border-r border-border/50 flex flex-col md:hidden shadow-xl"
          >
            {children}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
