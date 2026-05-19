---
name: High-Precision Developer Interface
colors:
  surface: '#051424'
  surface-dim: '#051424'
  surface-bright: '#2c3a4c'
  surface-container-lowest: '#010f1f'
  surface-container-low: '#0d1c2d'
  surface-container: '#122131'
  surface-container-high: '#1c2b3c'
  surface-container-highest: '#273647'
  on-surface: '#d4e4fa'
  on-surface-variant: '#bac9cc'
  inverse-surface: '#d4e4fa'
  inverse-on-surface: '#233143'
  outline: '#849396'
  outline-variant: '#3b494c'
  surface-tint: '#00daf3'
  primary: '#c3f5ff'
  on-primary: '#00363d'
  primary-container: '#00e5ff'
  on-primary-container: '#00626e'
  inverse-primary: '#006875'
  secondary: '#b7c8e1'
  on-secondary: '#213145'
  secondary-container: '#3a4a5f'
  on-secondary-container: '#a9bad3'
  tertiary: '#ffeac0'
  on-tertiary: '#3e2e00'
  tertiary-container: '#fec931'
  on-tertiary-container: '#6f5500'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#9cf0ff'
  primary-fixed-dim: '#00daf3'
  on-primary-fixed: '#001f24'
  on-primary-fixed-variant: '#004f58'
  secondary-fixed: '#d3e4fe'
  secondary-fixed-dim: '#b7c8e1'
  on-secondary-fixed: '#0b1c30'
  on-secondary-fixed-variant: '#38485d'
  tertiary-fixed: '#ffdf96'
  tertiary-fixed-dim: '#f3bf26'
  on-tertiary-fixed: '#251a00'
  on-tertiary-fixed-variant: '#594400'
  background: '#051424'
  on-background: '#d4e4fa'
  surface-variant: '#273647'
typography:
  headline-xl:
    fontFamily: Geist
    fontSize: 40px
    fontWeight: '600'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
  body-lg:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  label-caps:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 16px
  margin-mobile: 16px
  margin-desktop: 32px
---

## Brand & Style
The design system is engineered for a high-performance B2B SaaS environment where precision and clarity are paramount. The brand personality is **Expert, Efficient, and Reliable**, catering to developers and designers who require a tool that feels like a natural extension of their workflow.

The visual style leverages **Corporate Modernism** with a **Technical Minimalist** edge. We prioritize functional density—maximizing information without creating clutter. The interface uses a dark-mode-first approach to reduce eye strain during long sessions, utilizing subtle tonal shifts rather than heavy shadows to define hierarchy. Every element is intentional, removing decorative flourishes in favor of high-utility components that evoke a sense of sophisticated engineering.

## Colors
The palette is rooted in deep, monochromatic slates to establish a professional, "IDE-like" environment. 

- **Primary (Cursor Teal):** A high-vibrancy accent used sparingly for primary actions, active cursors, and progress indicators. It serves as the "beacon" of intelligence within the UI.
- **Surface Strategy:** 
    - **User Queries:** Rendered on a subtle Slate (#1E293B) to provide a distinct but integrated feel.
    - **AI Responses:** Rendered on a deeper Charcoal (#0F172A) to represent the "core" of the platform's intelligence.
- **Neutral Scales:** Used for borders, secondary text, and inactive states to maintain a low-contrast, high-focus environment.

## Typography
Typography is the backbone of this design system, emphasizing readability and technical precision. We use **Geist** for its clean, geometric grotesque qualities that mirror the precision of a code editor.

For technical metadata and code snippets, **JetBrains Mono** is utilized to provide a clear distinction between prose and logic. 
- **Hierarchy:** Use tight letter-spacing on larger headlines to maintain a compact, "designed" look. 
- **Body Text:** Use `body-md` for standard AI responses and `body-sm` for sidebar or secondary navigation elements.
- **Labels:** Use uppercase `label-caps` for section headers and category tags to create a rhythmic structure in dense layouts.

## Layout & Spacing
The system employs a **Fixed-Fluid Hybrid** grid. The primary workspace utilizes a fluid container to maximize code visibility, while sidebars and inspectors remain at fixed widths (e.g., 280px or 320px) to preserve predictability.

Spacing follows a **4px baseline rhythm**, ensuring that all elements align perfectly with monospaced text components. 
- **Desktop:** A 12-column grid for dashboard views, with content centered in a 1200px max-width container for reading-heavy documentation.
- **Gaps:** Use `md` (16px) for standard component spacing and `xs` (8px) for tightly related elements like label-input pairs.
- **Padding:** Message bubbles should use a consistent `lg` (24px) internal padding to ensure legibility in chat interfaces.

## Elevation & Depth
This design system avoids heavy drop shadows in favor of **Tonal Layering** and **Low-Contrast Outlines**.

Depth is communicated through brightness:
- **Level 0 (Background):** The darkest slate, used for the main application background.
- **Level 1 (Containers/Sidebars):** One step lighter, defined by a 1px solid border (#334155).
- **Level 2 (Popovers/Modals):** A subtle background blur (8px) combined with a slightly brighter surface color to simulate physical proximity to the user.

Shadows, when used (e.g., for detached modals), should be "Ink Shadows": deep, narrow, and high-opacity, mimicking the look of professional drafting software.

## Shapes
Shape language is restrained and architectural. We use a **Soft (0.25rem)** rounding strategy to soften the technical edge without appearing "consumer-grade" or playful.

- **Standard Elements:** Inputs, buttons, and chips use a 4px (0.25rem) radius.
- **Large Elements:** Cards and message bubbles use an 8px (0.5rem) radius to provide a clear container hierarchy.
- **Interactive States:** Use a distinct border-color change (to Primary Teal) rather than a shape change to indicate focus.

## Components
- **Buttons:** Minimalist execution. Primary buttons use a solid Teal fill with black text for maximum contrast. Secondary buttons use a ghost style with a subtle 1px border (#334155) and no fill until hover.
- **Input Fields:** Flat design with a dark background (#0F172A) and a 1px slate border. On focus, the border transitions to the primary teal with a subtle outer glow (0px 0px 0px 2px rgba(0, 229, 255, 0.2)).
- **Message Bubbles:** User queries are right-aligned with a subtle slate background. AI responses are left-aligned with a charcoal background and a vertical accent line of primary teal on the far left to indicate "Processing" or "System Origin."
- **Chips/Tags:** Monospaced font (`code-md`), small padding (2px 8px), and a background that is only 10% opacity of the text color to maintain a clean aesthetic.
- **Code Blocks:** Syntax highlighting should be customized to match the brand palette, using Teal for keywords and Slates for comments.