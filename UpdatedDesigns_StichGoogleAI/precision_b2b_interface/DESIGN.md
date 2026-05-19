---
name: Precision B2B Interface
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#3c494c'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#6c797d'
  outline-variant: '#bbc9cc'
  surface-tint: '#006877'
  primary: '#006877'
  on-primary: '#ffffff'
  primary-container: '#00bdd6'
  on-primary-container: '#004752'
  inverse-primary: '#43d8f2'
  secondary: '#545f73'
  on-secondary: '#ffffff'
  secondary-container: '#d5e0f8'
  on-secondary-container: '#586377'
  tertiary: '#505f76'
  on-tertiary: '#ffffff'
  tertiary-container: '#9dadc6'
  on-tertiary-container: '#314156'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#a2eeff'
  primary-fixed-dim: '#43d8f2'
  on-primary-fixed: '#001f25'
  on-primary-fixed-variant: '#004e5a'
  secondary-fixed: '#d8e3fb'
  secondary-fixed-dim: '#bcc7de'
  on-secondary-fixed: '#111c2d'
  on-secondary-fixed-variant: '#3c475a'
  tertiary-fixed: '#d3e4fe'
  tertiary-fixed-dim: '#b7c8e1'
  on-tertiary-fixed: '#0b1c30'
  on-tertiary-fixed-variant: '#38485d'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  headline-lg:
    fontFamily: Geist
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Geist
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  headline-lg-mobile:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 20px
  margin-mobile: 16px
  margin-desktop: 32px
---

## Brand & Style

This design system embodies a high-efficiency, professional B2B environment. It prioritizes clarity, systematic organization, and a "low-friction" user experience. The aesthetic is rooted in **Modern Corporate** principles with a heavy lean toward **Minimalism**. 

The target audience consists of power users and stakeholders who require high data density without cognitive overload. The UI evokes a sense of reliability and precision, using generous whitespace and a restrained color palette to direct focus toward content and critical actions.

## Colors

The palette is anchored by a crisp `#FFFFFF` background to maximize perceived brightness and cleanliness. Hierarchy is established through subtle shifts in grey scale rather than heavy lines:
- **Primary Teal (#00BDD6):** Reserved strictly for primary call-to-actions, active states, and focus indicators.
- **Surface Layering:** The sidebar utilizes `#F8FAFC` to create a distinct functional zone, while internal containers and card headers use `#F1F5F9` for grouping.
- **Typography Contrast:** We use a "Dark Slate" (`#1E293B`) for high-contrast headlines and "Medium Slate" (`#64748B`) for supporting metadata to ensure WCAG AA compliance and reduced eye strain.

## Typography

The design system utilizes **Geist** for its technical precision and exceptional legibility at small sizes. 
- **Scale:** A typographic scale with a 1.25 ratio ensures clear distinction between hierarchy levels.
- **Weight:** Medium (500) is used for UI labels and interactive elements, while Semibold (600) is reserved for headlines to maintain a professional, sturdy feel.
- **Rhythm:** Line heights are set to 1.5x for body text to improve readability in data-heavy views.

## Layout & Spacing

The layout follows a **Fluid Grid** model with a base-8 spacing system. 
- **Structure:** Content is organized into a 12-column grid on desktop, collapsing to 4 columns on mobile. 
- **Sidebar:** A fixed-width navigation sidebar (256px) remains on the left for desktop, providing a persistent anchor point.
- **Density:** Spacing is balanced between "Comfortable" for landing/marketing views and "Compact" for dashboard/data tables. Use `md (16px)` as the default padding for standard components.

## Elevation & Depth

This design system minimizes the use of shadows to maintain a clean, flat, professional look. Depth is conveyed primarily through **Tonal Layers**:
- **Level 0 (Background):** `#FFFFFF`.
- **Level 1 (In-page Containers):** `#F8FAFC`.
- **Level 2 (Secondary Elements/Hover):** `#F1F5F9`.
- **Subtle Outlines:** Instead of heavy shadows, use 1px borders in `#E2E8F0` to define card boundaries.
- **Floating Elements:** Only modals and dropdown menus receive a soft ambient shadow (0px 10px 15px -3px rgba(0, 0, 0, 0.05)) to separate them from the primary interface.

## Shapes

The shape language is sophisticated and modern. 
- **Radius:** A standard radius of `0.5rem (8px)` is used for most UI components (Inputs, Buttons, Cards).
- **Larger Elements:** Sections or main containers use `1rem (16px)` to create a softer, more contemporary container feel.
- **Consistency:** Roundness should be applied consistently to all interactive states, including focus rings and selection overlays.

## Components

- **Buttons:** Primary buttons use the Teal accent with white text. Secondary buttons use a slate outline or a light grey ghost style.
- **Inputs:** Clean, white background with a 1px slate-200 border. On focus, the border transitions to Teal with a soft 2px glow.
- **Cards:** White background with a subtle `#E2E8F0` border. Headers should have a `#F8FAFC` background to separate them from the card body.
- **Chips/Badges:** Use low-saturation background tints of the primary color for active states, or light grey for neutral tags, paired with medium-weight text.
- **Lists:** Rows should be separated by thin 1px lines (`#F1F5F9`). Use a subtle `#F8FAFC` hover state for list items to indicate interactivity.
- **Sidebars:** Integrated navigation with consistent Geist typography and Teal-colored vertical indicators for active menu items.