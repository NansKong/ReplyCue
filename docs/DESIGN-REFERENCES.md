# Design direction

Original composition: charcoal green surfaces, pale mint accents, Geist typography, a compact reader, visible focus states, and restrained opacity/position transitions. No template code, paid assets, or third-party brand marks were copied.

References reviewed on 2026-11-02:

- https://threeui.com/browse — interactive shaders, components, and dimensional compositions. Used as inspiration for the low-cost CSS grid/orbit stage; no WebGL runtime is shipped.
- https://supahero.io/ — hero section library; now points visitors toward ScreensDesign. Inspired a large typographic hero with a product preview and two clear actions.
- https://www.awwwards.com/awwwards/collections/free-fonts/ — typography discovery, including Geist. Geist is bundled locally through @fontsource/geist.
- https://curated.design/ — product and desktop-app page references, section hierarchy, and spacing.
- https://21st.dev/community/templates — React/Next.js landing and dashboard patterns, including glass-style examples.
- https://uiverse.io/ — interaction and component-state references. Buttons and controls here are original CSS.

Website progression: product promise → interactive reader → specific capabilities → setup steps → data flow → FAQs → working Windows download.

Desktop progression: résumé → role → explicit cloud consent → session. Transcript and Q&A use their own scrollable views. Keys live in a focused Connections dialog with keyboard trapping and focus restoration.

The website is server-rendered at build time, with client JS only for the demo and desktop workspace. Animations respect reduced-motion preferences. Decorative graphs are CSS/SVG rather than a graphics library. Fonts are served locally.

Technical references:
- https://nextjs.org/docs/app/guides/static-exports
- https://www.electronjs.org/docs/latest/tutorial/security
- https://pyinstaller.org/en/stable/runtime-information.html
- https://www.electron.build/win/
