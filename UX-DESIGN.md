# UX refresh — presentation only

Visual direction: graphite surfaces, pale mint interaction accents, quiet left navigation, soft structural borders, compact reading controls and a 300 ms eased panel transition. No native backdrop blur claim: the overlay remains a custom translucent surface.

References reviewed:
- Linear: https://linear.app/now/behind-the-latest-design-refresh
- Raycast: https://www.raycast.com/
- Apple glass material: https://developer.apple.com/documentation/TechnologyOverviews/liquid-glass

Changes: sidebar navigation bound to the existing four pages, revised setup typography and spacing, clearer primary action, visible provider-processing disclosure, component hover/pressed/focus/disabled states, custom check and stepper graphics, styled scrollbars and sliders, refined overlay gradient and rim highlight, shorter geometry transition, cursor hints and accessible names for reading controls.

Verification: cloud.py, groq_backend.py, replicate_backend.py, knowledge.py and settings.py match their pre-refresh SHA-256 hashes. All existing app methods outside constructors and paintEvent have identical parsed syntax trees. Checked minimum 860x660 setup bounds, sidebar/page binding, 14–34 px font controls, history mode, compact overlay control bounds, setup/overlay renders, 22 existing checks and startup smoke check. No cloud requests or API charges were needed for this refresh.
