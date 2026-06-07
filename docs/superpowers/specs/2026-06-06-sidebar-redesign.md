# Sidebar Redesign — Animated Sidebar for Admin & Chat

**Date**: 2026-06-06
**Scope**: Replace admin and chat sidebars with animated framer-motion style

## Design

### Shared Component: `components/ui/animated-sidebar.tsx`

Extract reusable animated primitives:
- `HamburgerToggle` — animated hamburger ↔ X icon (framer-motion SVG paths)
- `CollapsibleSection` — expand/collapse with AnimatePresence
- `ProfileSection` — avatar circle + username display (from AuthContext)
- Generic sidebar shell with mobile overlay (fixed inset-0 on md:hidden)

### Admin Sidebar (`components/layout/Sidebar.tsx` — rewrite)

```
Profile  (avatar + username from useAuth())
---------
Dashboard   → /admin
Collections → /admin/collections
Ingestion   → /admin/ingestion  (collapsible: Jobs → /admin/ingestion/jobs)
Chat        → /chat
```

- All items use `NavLink` with active state styling (rounded-xl, bg change)
- `Ingestion` is a CollapsibleSection containing `Jobs` sub-link
- `Chat` is the last nav item, same level as others (no border separator)
- Desktop: fixed w-64 sidebar
- Mobile: overlay triggered by hamburger in top bar

### Chat Sidebar (`routes/chat/ChatLayout.tsx` — modify)

```
Profile  (avatar + username from useAuth())
---------
Collection select dropdown
---------
New Session button
---------
SessionList (existing)
---------
Admin → /admin
```

- Same animated hamburger toggle for mobile
- Same profile section at top
- All existing functionality preserved (collections select, session CRUD, new session)
- `Admin` link at bottom of sidebar (moved from header)

## Files

| File | Action |
|------|--------|
| `components/ui/animated-sidebar.tsx` | NEW — shared animated primitives |
| `components/layout/Sidebar.tsx` | REWRITE — admin sidebar |
| `routes/chat/ChatLayout.tsx` | MODIFY — chat sidebar restyle |
| `package.json` | ADD `framer-motion` dependency |

## Labels

All navigation labels in English, no emoji.

## Not Changed

- Routes, AuthContext, App.tsx router structure
- Collections select, SessionList, ChatView
- Existing shadcn/ui color tokens