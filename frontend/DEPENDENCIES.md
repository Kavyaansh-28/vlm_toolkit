# Rajasthan Explorer AI — Frontend Notes

## Overview

This project is a frontend-only, responsive concept application for conversational Rajasthan trip planning. It contains no backend, authentication, database, booking integration, or live travel API.

## Runtime dependencies

| Package | Purpose |
| --- | --- |
| `react` | Component rendering and local interaction state |
| `react-dom` | Browser DOM mounting |

No component library, icon package, mapping SDK, or chart package was added. The interface uses:

- A small in-file SVG icon system.
- CSS layout and responsive breakpoints.
- A stylised inline SVG route illustration, not a geographic or live map.
- React local state for the mobile drawer, local-knowledge toggle, evidence accordion, mobile trip-details panel, suggestion selection, and follow-up comparison preview.

## Development dependencies

| Package | Purpose |
| --- | --- |
| `vite` | Development and production bundling |
| `typescript` | Static typing |
| `@vitejs/plugin-react` | React support in Vite |
| `tailwindcss` and `@tailwindcss/vite` | Available styling toolchain |
| `oxfmt` | Repository formatter |
| React and Node type packages | Type definitions |

## Fonts

The UI imports two public Google Font families in `src/index.css`:

- **DM Sans** for interface text.
- **Playfair Display** for restrained editorial headings and destination titles.

If remote fonts are unavailable, the browser falls back to generic `sans-serif` and `serif` families.

## Main files

- `src/App.tsx` — interface components, content, SVG icons, and local UI state.
- `src/index.css` — design tokens, component styling, responsive desktop/tablet/mobile layouts.
- `src/main.tsx` — React entry point.

## Data and trust labels

All displayed prices are explicitly presented as planning estimates. The interface distinguishes:

- Local knowledge
- Planning estimate
- Needs confirmation
- Within budget
- Live result (component style is defined, but no live result is fabricated)

No hotel availability, star ratings, review counts, live weather, permit availability, or booking prices are claimed.

## Responsive behavior

- Desktop: persistent 278 px navigation, central conversation, and contextual trip panel.
- Tablet: navigation becomes a slide-out drawer.
- Mobile (390 px target): stacked chat, compact timeline cards, fixed composer, and collapsible trip-details panel.

## Commands

The Vite development server is managed by Figma Make and should not be started manually.

```sh
pnpm build
pnpm format
```

## Future integration boundaries

If a backend is added later, appropriate integration points are:

1. Conversation submission in `Composer`.
2. RAG evidence payload in `Evidence`.
3. Live hotel, restaurant, weather, permit, and transit providers.
4. Saved plans and user journey persistence.
5. Export generation.

Any live provider response should keep source timestamps and maintain the existing `Live result`, `Estimate`, and `Needs confirmation` distinction.
