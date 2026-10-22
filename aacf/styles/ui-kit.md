# UI Kit — Component Library Definitions

## Design System

### Buttons
| Variant | Usage | Classes |
|---------|-------|---------|
| Primary | Main actions | `bg-primary text-primary-foreground hover:bg-primary/90` |
| Secondary | Secondary actions | `bg-secondary text-secondary-foreground hover:bg-secondary/80` |
| Destructive | Delete/remove | `bg-destructive text-destructive-foreground hover:bg-destructive/90` |
| Outline | Tertiary actions | `border border-input bg-background hover:bg-accent` |
| Ghost | Inline actions | `hover:bg-accent hover:text-accent-foreground` |
| Icon | Icon-only buttons | `h-10 w-10 rounded-full` |

### Forms
- Use `shadcn/ui` Form components with react-hook-form + zod validation
- Label always above input
- Error messages below input in destructive color
- Required fields marked with asterisk
- Submit buttons disabled during loading (show spinner)

### Tables
- Use `shadcn/ui` DataTable with TanStack Table
- Sortable columns with header click
- Pagination: 10/25/50 items per page
- Search/filter bar above table
- Row actions via dropdown menu (end column)
- Loading skeleton rows while fetching

### Navigation
- Sidebar for main navigation (collapsible)
- Breadcrumbs for deep pages
- Tabs for sub-sections within a page
- Command palette (Ctrl+K) for quick navigation

### Cards
- Standard card: border, rounded-lg, p-6, shadow-sm
- Hover: translate-y-[-2px] shadow-md transition
- Status indicator: colored left border
- Click: navigate to detail view

### Modals/Dialogs
- Use `shadcn/ui` Dialog component
- Centered, max-width-lg
- Close button top-right
- Backdrop click to dismiss (unless form has changes)
- Focus trap for accessibility

### Toast/Notifications
- Use `sonner` for toast notifications
- Position: bottom-right
- Auto-dismiss: 5 seconds
- Types: success (green), error (red), warning (amber), info (blue)
