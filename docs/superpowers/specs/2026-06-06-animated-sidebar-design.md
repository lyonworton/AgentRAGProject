# Animated Sidebar Redesign

**Date**: 2026-06-06
**Scope**: Admin + Chat sidebar visual overhaul with framer-motion animations

## Goal

Replace the static admin and chat sidebars with animated framer-motion components while preserving all existing routes, functionality, and data flow.

## Changes

### New File
- `components/ui/animated-sidebar.tsx` — Shared primitives: `AnimatedMenuToggle`, `CollapsibleSection`, `ProfileSection`

### Modified Files
- `components/layout/Sidebar.tsx` — Admin sidebar: animated style, profile header, navigation items (Dashboard, Collections, Ingestion, Jobs, Chat)
- `routes/chat/ChatLayout.tsx` — Chat sidebar: animated style, profile header, collection selector, new session button, session list, admin link

### New Dependency
- `framer-motion` — npm package for sidebar animations

## Design

### Admin Sidebar
```
┌──────────────┐
│ Profile      │  avatar + username from AuthContext
├──────────────┤
│ Dashboard    │  NavLink to /admin
│ Collections  │  NavLink to /admin/collections
│ Ingestion    │  NavLink to /admin/ingestion
│ Jobs         │  NavLink to /admin/ingestion/jobs
│ Chat         │  NavLink to /chat (last item, same level)
└──────────────┘
```

### Chat Sidebar
```
┌──────────────┐
│ Profile      │  avatar + username from AuthContext
├──────────────┤
│ Collection   │  select dropdown (existing)
│ Selector     │
├──────────────┤
│ + New        │  navigate to /chat
│ Session      │
├──────────────┤
│ Session      │  existing SessionList component
│ List         │
├──────────────┤
│ Admin        │  Link to /admin
└──────────────┘
```

## Animation Details
- Mobile: fixed overlay sidebar slides in from left (framer-motion AnimatePresence)
- Desktop: always visible, w-64, white background with shadow
- Hamburger toggle: animated SVG morphing (3 lines to X)
- Nav items: rounded-xl pill buttons with hover:bg-gray-100

## What Stays the Same
- All routes and React Router v6 structure
- AuthContext (useAuth hook for user data)
- Collection selector, SessionList, ChatView
- Tailwind CSS + shadcn/ui token system
- Translation: all text in English, no emoji

## Verification
- tsc --noEmit: zero errors
- npm run build: successful
- Both /admin and /chat render with new sidebar
- Mobile toggle works
- Nav links navigate correctly