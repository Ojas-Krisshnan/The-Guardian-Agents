---
name: ui-ux-pro-max
description: Primary design system and UX design skill for web and mobile interfaces. Use for layout, visual hierarchy, typography scale, semantic color systems, consistent spacing, component design, responsive layouts, dashboard design, and interaction patterns.
---

# UI/UX Pro Max — Design System & Interaction Architecture

> Purpose: Primary Design System / UX Design implementation.
> Defines structured design tokens, component hierarchies, responsive grids, form ergonomics, and accessible interaction patterns.

## 1. DESIGN SYSTEM SPECIFICATION

### A. Semantic Color Palette
- **Background**: `#0b0f19` (Deep Obsidian / Slate 950)
- **Surface**: `#111827` (Slate 900)
- **Elevated Surface**: `#1e293b` (Slate 800)
- **Border Subtle**: `rgba(255, 255, 255, 0.08)`
- **Border Medium**: `rgba(255, 255, 255, 0.15)`
- **Primary Accent**: `#3b82f6` (Refined Blue) / `#6366f1` (Indigo)
- **Success / Mastery**: `#10b981` (Emerald 500)
- **Warning / Review**: `#f59e0b` (Amber 500)
- **Error / Misconception**: `#ef4444` (Rose 500)
- **Text Primary**: `#f8fafc` (Slate 50)
- **Text Secondary**: `#94a3b8` (Slate 400)
- **Text Muted**: `#64748b` (Slate 500)

### B. Typography Scale
- **Display**: `2.25rem` (36px), font-weight: 700, letter-spacing: -0.025em, line-height: 1.15
- **Heading 1**: `1.75rem` (28px), font-weight: 700, letter-spacing: -0.02em, line-height: 1.25
- **Heading 2**: `1.25rem` (20px), font-weight: 600, letter-spacing: -0.015em, line-height: 1.35
- **Heading 3**: `1.05rem` (16.8px), font-weight: 600, letter-spacing: -0.01em, line-height: 1.4
- **Body Regular**: `0.9375rem` (15px), font-weight: 400, line-height: 1.55
- **Caption / Metadata**: `0.8125rem` (13px), font-weight: 500, line-height: 1.4

### C. Spacing System (8pt Grid)
- `xxs`: `0.25rem` (4px)
- `xs`: `0.5rem` (8px)
- `sm`: `0.75rem` (12px)
- `md`: `1rem` (16px)
- `lg`: `1.5rem` (24px)
- `xl`: `2rem` (32px)
- `2xl`: `3rem` (48px)

### D. Component Consistency Guidelines
1. **Buttons**:
   - Primary: Solid background, subtle shadow, 10px radius, 40px min height.
   - Secondary / Ghost: Clean 1px border, muted text, transparent background.
   - Focus ring: `2px solid #3b82f6` with `2px` offset.
2. **Cards**:
   - Flat slate background, 1px border, 12px radius, no garish neon outer glows.
   - Hover state: `translateY(-2px)` with subtle natural drop shadow.
3. **Inputs & Selects**:
   - Clear labels above fields, 14px text, 40px touch targets, explicit focus borders.
4. **Modals & Dialogs**:
   - Centered backdrop with `rgba(0, 0, 0, 0.65)`, clean close button, clear header and action footer.
5. **Dashboard Hierarchy**:
   - Header with active title and user identity.
   - Key stats row (grid of clean metric cards).
   - Main workspace (tabs, test view, concept cards, notes) with prominent empty states.
