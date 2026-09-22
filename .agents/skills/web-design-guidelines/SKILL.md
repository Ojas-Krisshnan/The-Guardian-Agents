---
name: web-design-guidelines
description: Final UI quality and web design guidelines audit skill. Use for auditing accessibility, contrast ratios, touch targets, keyboard navigation, responsive behavior, visual hierarchy, interaction consistency, and detecting UI regressions.
---

# Web Design Guidelines — Quality & Usability Audit

> Purpose: Final UI Quality / Usability Audit.
> Audits interface implementations against Web Interface Guidelines, WCAG accessibility standards, and web usability best practices.

## 1. AUDIT CATEGORIES & CRITERIA

### A. Accessibility & Usability (CRITICAL)
- [ ] **Contrast**: Text elements meet WCAG AA minimum 4.5:1 ratio against background.
- [ ] **Keyboard Navigation**: All interactive elements (buttons, inputs, links, cards) are reachable via Tab and activatable via Enter/Space.
- [ ] **Focus States**: High-visibility `:focus-visible` rings present without being obscured or removed.
- [ ] **Touch Targets**: Minimum target size 44×44px on mobile and touch devices.
- [ ] **Form Labels**: Inputs have explicit or aria-associated labels, not placeholder-only hints.

### B. Responsive & Layout Behavior (HIGH)
- [ ] **No Horizontal Scroll**: Zero viewport overflow across 320px (mobile), 768px (tablet), 1024px (laptop), and 1440px (desktop).
- [ ] **Flexible Grids**: Cards and dashboards reflow into single columns gracefully on small screens.
- [ ] **Text Wrapping & Truncation**: No broken text overflow or clipped buttons.

### C. Visual Hierarchy & Typography (MEDIUM)
- [ ] **Single Primary Focus**: Each screen has one clear focal point.
- [ ] **Heading Proportions**: Clear semantic scale (`h1` > `h2` > `h3` > body).
- [ ] **Status Feedback**: Loading states indicate progress; empty states guide the user clearly.

### D. Motion & Reduced Motion (MEDIUM)
- [ ] **Reduced Motion**: Respects `@media (prefers-reduced-motion: reduce)` by disabling non-essential transforms.
- [ ] **Duration Bounds**: Transitions are bounded (150-250ms), never disorienting.
