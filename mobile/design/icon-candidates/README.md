# GPU Checker icon candidates

Generated with the built-in image_gen tool; no API/CLI fallback. User selected **B2** on 2026-11-11.

- A-compute.png: sapphire compute chip, cyan check and telemetry, dark navy, minimal dimensional silhouette.
- B-reactor-original.png: brushed titanium hexagonal reactor, three blades, cyan core, tiny amber status light.
- C-orbital.png: sapphire compute sphere/cube, sky-blue orbital band, mint satellite, telemetry pulse.
- B2-reactor-selected.png: approved edit of B, square-like chamfered octagon and four blades.

The approved original is archived. Its transparent centered cutout is copied to `mobile/public/branding/gpu-checker-b2.png` and `assets/app.png`. Android resources use the original bitmap with adaptive-layer inset; Windows ICO encoding contains 16, 24, 32, 48, 64, 128 and 256 px frames.

Final B2 edit prompt:

Edit this app-icon design. Preserve its dark brushed titanium material, luminous cyan reactor core, tiny amber status light, restrained dimensional mecha aesthetic, dark full-bleed background, premium finish and overall identity. Two precise changes: (1) make the housing more square and compact, but still clearly eight-sided: a regular square-like silhouette with four long horizontal/vertical sides and four shorter 45-degree chamfered corners, equal width and height, strong square-octagonal profile rather than a tall elongated polygon; (2) replace the three internal turbine blades with EXACTLY FOUR large clean curved metallic blades, evenly spaced at 90 degrees, rotating around the same bright cyan core. Maintain symmetry, clearly separated four blades and good legibility when downscaled to an Android launcher icon. Essential design within central 70 percent, ample safe margin for circular adaptive masks. One square icon only. No text, no labels, no mockup, no collage, no watermarks. Do not change palette to other colors.

2026-11-11 correction: B2-transparent-centered.png is the production alpha-transparent cutout, created with built-in image_gen (no API fallback). The exterior background was removed while retaining all internal dark surfaces. Packaging centers the alpha bounds with equal safe margins. The in-app logo is transparent. Android launcher background is approved ink navy (#0C192A) for MIUI consistency; desktop stays transparent. Final prompt: see ../../../assets/icon-prompt.txt.

Android 1.0.9: launcher uses a white adaptive background and 20.5% fractional foreground insets (density independent). A native rendering check verifies the full housing fits the circular mask at three densities and three pixel sizes.

Android 1.0.11 integrates the approved ink-navy launcher background and sliding process panel. The fixed oval inset reflection was removed; only the moving glow remains.
