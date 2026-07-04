---
name: Obsidian Electric
colors:
  surface: '#131313'
  surface-dim: '#131313'
  surface-bright: '#393939'
  surface-container-lowest: '#0e0e0e'
  surface-container-low: '#1c1b1b'
  surface-container: '#201f1f'
  surface-container-high: '#2a2a2a'
  surface-container-highest: '#353534'
  on-surface: '#e5e2e1'
  on-surface-variant: '#bac9cd'
  inverse-surface: '#e5e2e1'
  inverse-on-surface: '#313030'
  outline: '#859397'
  outline-variant: '#3b494c'
  surface-tint: '#00daf8'
  primary: '#baf2ff'
  on-primary: '#00363f'
  primary-container: '#00e0ff'
  on-primary-container: '#005f6d'
  inverse-primary: '#006877'
  secondary: '#dfb7ff'
  on-secondary: '#4b007e'
  secondary-container: '#9d05ff'
  on-secondary-container: '#f7e6ff'
  tertiary: '#e8e8e8'
  on-tertiary: '#303030'
  tertiary-container: '#cccccc'
  on-tertiary-container: '#565656'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#a5eeff'
  primary-fixed-dim: '#00daf8'
  on-primary-fixed: '#001f25'
  on-primary-fixed-variant: '#004e5a'
  secondary-fixed: '#f1daff'
  secondary-fixed-dim: '#dfb7ff'
  on-secondary-fixed: '#2d004f'
  on-secondary-fixed-variant: '#6b00b0'
  tertiary-fixed: '#e2e2e2'
  tertiary-fixed-dim: '#c6c6c6'
  on-tertiary-fixed: '#1b1b1b'
  on-tertiary-fixed-variant: '#474747'
  background: '#131313'
  on-background: '#e5e2e1'
  surface-variant: '#353534'
typography:
  headline-xl:
    fontFamily: Sora
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Sora
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Sora
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
  headline-md:
    fontFamily: Sora
    fontSize: 24px
    fontWeight: '600'
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
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.08em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 8px
  container-padding-desktop: 64px
  container-padding-mobile: 24px
  gutter-desktop: 32px
  gutter-mobile: 16px
  card-padding-internal: 32px
  stack-gap: 24px
---

## Brand & Style

This design system explores a "Full Black" aesthetic, targeting high-end technology, gaming, or premium creative platforms. The brand personality is mysterious, high-performance, and futuristic. It leverages a modified **Glassmorphism** and **High-Contrast** mix to ensure that while the backdrop is a void-like pure black, the interactive elements vibrate with energy.

The emotional response should be one of "Digital Luxury"—where the absence of light emphasizes the precision of the vibrant accents. By utilizing deep greys for surfaces and neon gradients for calls to action, the UI creates a focused environment that reduces eye strain while maintaining a high-impact visual identity.

## Colors

The palette is anchored by a true black `#000000` background. To maintain depth without losing the "Full Black" intent, surfaces are constructed from a spectrum of near-black greys. 

**Accents:**
- **Electric Blue (#00E0FF):** Used for primary actions, success states, and active indicators.
- **Neon Purple (#9D00FF):** Used for secondary highlights and deep decorative gradients.
- **The Obsidian Gradient:** A 135-degree blend of Electric Blue and Neon Purple, reserved for high-level calls to action and hero elements.

**Typography Contrast:**
Small text and labels utilize High-Contrast Whites (`#F5F5F5`) to ensure maximum legibility against the dark backgrounds, while secondary text uses a slightly muted but still crisp light grey.

## Typography

This design system uses a triple-font strategy to balance character and precision. 
- **Sora** provides a bold, geometric presence for headlines, reflecting the futuristic theme. 
- **Geist** offers a highly legible, technical feel for body copy, ensuring clarity in long-form text against dark backgrounds. 
- **JetBrains Mono** is utilized for labels and metadata, reinforcing the "developer-tool" or high-performance aesthetic.

Small labels use `letter-spacing` and `uppercase` transforms to ensure they remain readable even at minimal sizes. All typography should maintain a minimum contrast ratio of 7:1 against their respective surface colors.

## Layout & Spacing

The layout philosophy follows an "Airy Premium" model, favoring generous whitespace to prevent the dark theme from feeling cramped or heavy. 

A **12-column fluid grid** is used for desktop, transitioning to a **4-column grid** for mobile. Internal card padding has been increased to `32px` to allow content to "breathe" within its high-contrast borders. 

Vertical spacing between sections should be expansive, using the `stack-gap` or multiples of the `8px` base unit to create clear visual rhythm. Margin and gutter widths are wider than standard to emphasize the cinematic, wide-screen nature of the design system.

## Elevation & Depth

In this design system, depth is communicated through a "Layered Void" approach. Instead of traditional light-source shadows, we use:

1.  **Subtle Outlines:** Every surface (cards, modals, inputs) features a delicate `1px` border. The border color should be `rgba(255, 255, 255, 0.1)` for lower surfaces and `rgba(255, 255, 255, 0.2)` for higher surfaces.
2.  **Deep Ambient Shadows:** To separate a surface from the pure black background, use a soft, large-radius shadow: `0 20px 40px rgba(0, 0, 0, 0.8)`. 
3.  **Tonal Tiers:** Objects physically "higher" in the stack use progressively lighter surface greys (e.g., a modal uses `surface-high` while the page beneath it uses `surface-low`).
4.  **Accent Glows:** High-priority elements may use a subtle outer glow (drop shadow) using the Electric Blue primary color with a high blur and low opacity (15-20%) to simulate a neon effect.

## Shapes

The shape language is "Soft" yet precise. Elements use a `0.25rem` (4px) base corner radius to maintain a technical, sharp-edged feel while avoiding the harshness of 0px corners. 

- Large containers (cards, modals) use `rounded-lg` (8px).
- Extreme elements (buttons, tags) may occasionally use `rounded-xl` (12px) for contrast, but never full pill shapes, to keep the design feeling structured and architectural.

## Components

**Buttons:**
Primary buttons feature the Obsidian Gradient with white text. Secondary buttons are "Ghost" style: `1px` Electric Blue border with high-contrast white text. Hover states should include a subtle `0 0 15px` glow in the primary color.

**Cards:**
Cards utilize the `surface-mid` background with `card-padding-internal`. They must have the `1px` subtle border to distinguish them from the pure black background.

**Inputs:**
Fields use `surface-low` with a `1px` border of `white @ 10%`. Upon focus, the border transitions to Electric Blue, and a very faint blue inner glow is applied. Labels sit above the input using the `label-md` typography.

**Chips/Tags:**
Small, high-contrast badges using `surface-high` and `label-sm` text. Active chips utilize a solid Electric Blue background with black text for maximum "pop."

**Lists:**
List items are separated by `1px` borders (`white @ 5%`). High-contrast white is used for primary list text, with Electric Blue used for icons or action indicators.