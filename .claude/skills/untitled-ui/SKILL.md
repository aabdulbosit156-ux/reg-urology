---
name: untitled-ui
description: Build and style React UI in frontend/ using Untitled UI React (Tailwind CSS v4 + React Aria Components). Use whenever creating or editing any component/page under frontend/src, adding a new UI element, choosing Tailwind classes, or picking/wiring an icon. Covers the CLI (add/search/example), the untitledui MCP server, naming conventions, and semantic color tokens. See reference.md for the full component API and color token tables.
---

# Untitled UI React

`frontend/` is a Vite + React 19 + TypeScript app scaffolded from the official
`untitledui-vite-starter-kit`. Components are **copied into the repo**, not
installed as an opaque dependency — `frontend/src/components/**` is source
code you own and can edit directly.

## Before writing a component by hand

Prefer pulling from the library over hand-rolling JSX:

- Search first: `npx untitledui@latest search "<natural language query>"`
  (e.g. `"pricing table with toggle"`, `"dark login form"`).
- Add a specific component: `npx untitledui@latest add <name>` (run from
  `frontend/`), e.g. `npx untitledui@latest add button command-menu`.
- Add a full page example: `npx untitledui@latest example <name>`.
- The `untitledui` MCP server is registered for this project (see
  `.mcp.json`) — its tools (`search_components`, `get_component`,
  `get_page_templates`, icon search) can be called directly instead of
  shelling out to the CLI when you already have MCP tool access.

Only hand-write a component when nothing in the library fits, and then put it
in the matching folder (`components/base/`, `components/application/`,
`components/marketing/`, etc.) following the same patterns as neighboring
files.

## Non-negotiable conventions

- **File names are kebab-case.** `date-picker.tsx`, not `DatePicker.tsx`.
- **Prefix raw React Aria imports with `Aria`**: `import { Button as AriaButton } from "react-aria-components"`. Never import an unprefixed React Aria primitive that shadows a library component name.
- **Never use raw Tailwind palette classes** (`text-gray-900`, `bg-blue-700`). Always use the semantic tokens (`text-primary`, `bg-brand-solid`, `border-secondary`, `fg-error-primary`, ...) defined in `frontend/src/styles/theme.css` — they're what makes light/dark mode work. Full token tables are in `reference.md`.
- **Disabled state is `disabled:opacity-50`**, not per-token disabled colors (that was the old v7 pattern).
- Icons come from `@untitledui/icons` (free) — import by name (`import { ChevronDown } from "@untitledui/icons"`), pass as a component reference to `iconLeading`/`iconTrailing` props, or as a JSX element with `data-icon` if you need extra props. Size with `size-4`/`size-5`/`size-6`.
- Default small-transition class: `transition duration-100 ease-linear`.

## Brand color

The brand color scale lives in `frontend/src/styles/theme.css` as
`--color-brand-25` through `--color-brand-950`. Change the whole app's accent
color by replacing that one scale (keep all 12 steps, light→dark, for
contrast to hold up in both themes) — don't hunt for hardcoded colors
elsewhere.

## Commands

```bash
cd frontend
npm run dev      # http://localhost:5173
npm run build    # tsc -b && vite build
```

## Reference

Full component prop tables (Button, Input, Select, Checkbox, Badge, Avatar,
FeaturedIcon, links) and the complete text/border/foreground/background
semantic color token tables are in [reference.md](reference.md). Load it when
you need exact prop names/types or the full color token list — don't guess
them.
