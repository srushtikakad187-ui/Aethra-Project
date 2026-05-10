---
name: Aethra Gold
colors:
  surface: '#fcf8fa'
  surface-dim: '#dcd9db'
  surface-bright: '#fcf8fa'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f3f4'
  surface-container: '#f0edee'
  surface-container-high: '#eae7e9'
  surface-container-highest: '#e5e2e3'
  on-surface: '#1b1b1d'
  on-surface-variant: '#45464c'
  inverse-surface: '#303031'
  inverse-on-surface: '#f3f0f1'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#575e70'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#151b2b'
  on-primary-container: '#7d8497'
  inverse-primary: '#c0c6db'
  secondary: '#775a19'
  on-secondary: '#ffffff'
  secondary-container: '#fed488'
  on-secondary-container: '#785a1a'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#151c27'
  on-tertiary-container: '#7d8492'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dce2f8'
  primary-fixed-dim: '#c0c6db'
  on-primary-fixed: '#151b2b'
  on-primary-fixed-variant: '#404758'
  secondary-fixed: '#ffdea5'
  secondary-fixed-dim: '#e9c176'
  on-secondary-fixed: '#261900'
  on-secondary-fixed-variant: '#5d4201'
  tertiary-fixed: '#dce2f3'
  tertiary-fixed-dim: '#c0c7d6'
  on-tertiary-fixed: '#151c27'
  on-tertiary-fixed-variant: '#404754'
  background: '#fcf8fa'
  on-background: '#1b1b1d'
  surface-variant: '#e5e2e3'
typography:
  display-lg:
    fontFamily: Playfair Display
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Playfair Display
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.3'
  headline-lg-mobile:
    fontFamily: Playfair Display
    fontSize: 28px
    fontWeight: '600'
    lineHeight: '1.3'
  headline-md:
    fontFamily: Playfair Display
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: '1.2'
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: 0.05em
  data-mono:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: '1.4'
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 8px
  container-max: 1280px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 40px
  section-gap: 80px
---

## Brand & Style

This design system is engineered for a high-end enterprise environment where precision and prestige are paramount. The aesthetic follows a **Corporate / Modern** philosophy, infused with a minimalist editorial flair to reflect the "Gold" standard of assessment.

The UI evokes a sense of "AI-powered authority"—it is calm, spacious, and deliberate. By utilizing deep, nocturnal blues as the foundation and metallic gold as a strategic accent, the system establishes immediate trust and signifies premium value. Visual complexity is minimized to allow data and insights to take center stage, using generous whitespace to prevent cognitive overload during intensive assessment tasks.

## Colors

The palette is anchored by **Deep Navy (#0B1221)**, providing a sophisticated, stable foundation for text and primary branding. **Metallic Gold (#C5A059)** is used exclusively for "high-value" moments: primary actions, progress indicators, and successful assessment outcomes. 

**Slate Grey (#6B7280)** serves as the secondary UI color for supporting text, icons, and borders, ensuring the interface remains balanced and professional. The background is a crisp, sterile **White**, creating a high-contrast environment that improves readability and emphasizes the premium nature of the content.

## Typography

The typographic hierarchy utilizes a dual-font strategy. **Playfair Display** is reserved for headlines and brand-heavy moments, conveying a timeless, editorial elegance. Its high-contrast strokes signal luxury and prestige.

**Inter** is the workhorse for all functional UI elements, data visualizations, and body copy. It provides maximum legibility and a modern, technical feel that balances the traditional serif headers. For data-heavy tables or AI-generated scores, ensure `tnum` (tabular numerals) is enabled to maintain vertical alignment of figures.

## Layout & Spacing

The layout utilizes a **Fixed Grid** model on desktop (12 columns) to maintain a controlled, high-end presentation. On mobile, it transitions to a fluid single-column layout with 16px margins.

Spacing is governed by an 8px base unit, but the design system emphasizes "generous breathing room." Section gaps are intentionally large (80px+) to separate different phases of the assessment process, creating a focused, linear user journey. Elements should feel uncrowded; if in doubt, increase the white space to enhance the premium feel.

## Elevation & Depth

Visual hierarchy is established through **Tonal Layers** and **Ambient Shadows**. Surfaces are primarily flat, but high-priority containers (like Assessment Summary Cards) use a subtle, extra-diffused shadow: `0 4px 20px -2px rgba(11, 18, 33, 0.05)`.

To signify AI-powered modules, use a light "Slate Grey" 1px border with a very soft inner glow, suggesting a layer of intelligence beneath the surface. Avoid heavy drop shadows; depth should feel natural and light, as if paper layers are resting gently on a gallery wall.

## Shapes

The design system employs a **Soft (0.25rem)** roundedness. This subtle curvature softens the "Deep Navy" architecture without appearing overly playful or consumer-grade. 

- **Standard Buttons & Inputs:** 4px radius (Soft).
- **Cards & Modal Containers:** 8px radius (Rounded-lg).
- **Status Chips:** Full pill-shape to distinguish them from interactive buttons.
- **Iconography:** Use line-based icons with a 1.5pt stroke weight and slightly rounded caps to match the UI shape language.

## Components

### Buttons
*   **Primary:** Solid Metallic Gold (#C5A059) with White text. No gradient. High-contrast hover state (slight darken).
*   **Secondary:** Ghost style with a Deep Navy border and text.
*   **Tertiary:** Text-only in Deep Navy with an underlined Gold hover state.

### Input Fields
Inputs should have a minimal 1px border in Slate Grey. On focus, the border transitions to Deep Navy with a subtle Gold 2px outer glow. Labels are always positioned above the field in `label-sm` (uppercase).

### Cards
Cards are the primary container for assessment data. Use a white background, a 1px Slate Grey border (30% opacity), and the standard subtle ambient shadow. Headlines within cards should use the serif font.

### Assessment Specifics
*   **Progress Indicators:** Use thin, horizontal Gold bars.
*   **AI Insight Chips:** Use a light Deep Navy background (5% opacity) with a small Gold spark icon to denote "AI-powered" content.
*   **Data Tables:** Clean, no vertical lines. Use Deep Navy for headers and Slate Grey for row dividers.