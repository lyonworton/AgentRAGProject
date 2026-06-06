import { useState, type ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { User } from "lucide-react";

/* ── AnimatedMenuToggle ── */
export function AnimatedMenuToggle({
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
            strokeWidth="3"
            stroke="currentColor"
            strokeLinecap="round"
            variants={{
              closed: { d: "M 2 2.5 L 22 2.5" },
              open: { d: "M 3 16.5 L 17 2.5" },
            }}
          />
          <motion.path
            fill="transparent"
            strokeWidth="3"
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
            strokeWidth="3"
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

/* ── ProfileSection ── */
export function ProfileSection({
  username,
  email,
}: {
  username: string;
  email?: string;
}) {
  return (
    <div className="p-4 border-b border-border">
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 bg-muted rounded-full flex items-center justify-center shrink-0">
          <User className="h-5 w-5 text-muted-foreground" />
        </div>
        <div className="min-w-0">
          <p className="font-semibold text-sm truncate">{username}</p>
          {email && (
            <p className="text-xs text-muted-foreground truncate">{email}</p>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── MobileSidebar ── */
export function MobileSidebar({
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
          {/* backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="md:hidden fixed inset-0 bg-black/40 z-40"
            onClick={onClose}
          />
          {/* panel */}
          <motion.div
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            className="md:hidden fixed inset-y-0 left-0 z-50 w-64 bg-background text-foreground shadow-xl flex flex-col"
          >
            {children}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

/* ── DesktopSidebar ── */
export function DesktopSidebar({ children }: { children: ReactNode }) {
  return (
    <div className="hidden md:flex flex-col fixed top-0 left-0 h-full w-64 bg-background text-foreground border-r shadow-sm">
      {children}
    </div>
  );
}