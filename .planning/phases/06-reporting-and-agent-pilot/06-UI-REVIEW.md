# Phase 06 — UI Review

**Audited:** 2026-10-26
**Baseline:** abstract 6-pillar standards (no UI-SPEC.md for this phase)
**Screenshots:** not captured (code-only audit by instruction: no browser, no dev server)
**Interaction captures:** off (workflow.ui_interaction_capture is false)

Scope: the static progress page from `tools/progress.py` (`render_html`, `_page_css`, `render_svg`), checked against the local build `build/progress-page/index.html`. The owner passed UAT on this page, so every finding below is an advisory WARNING. None is a BLOCKER.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Exact, honest copy. "0.0091% of code bytes" leads the figures where a function ratio would read better, and the strip key sits after both strips |
| 2. Visuals | 2/4 | At current values the bar shows almost nothing, and the 1200x800 mosaic shrinks to about 31% on a phone, so its labels come out near 3.5 px |
| 3. Color | 3/4 | One token set, contrast measured in both schemes. The bar and mosaic tell matched from unmatched by hue alone (1.38:1 luminance) |
| 4. Typography | 4/4 | Five sizes on one system-ui stack, three weights, tabular numbers on the figures |
| 5. Spacing | 3/4 | A consistent rem rhythm. `main` has no `margin-inline:auto`, so wide screens left-align it, and the px tick constants sit outside the rem scale |
| 6. Experience Design | 2/4 | Tooltips live in `title` on 2 px ticks and SVG rects: no hover on touch, no keyboard focus, and the strip's `role="img"` hides them from assistive tech |

**Overall: 17/24**

---

## Top 3 Priority Fixes

1. **The partial and matched tooltips only work with a mouse.** Phone, keyboard and screen-reader users cannot read "func_000C6287: 53 bytes, partial, best 61.87%". The `title` attribute in `_tick_html` (progress.py:1068-1075) needs a hover, and a 2x14 px tick is far below a usable touch target. Fix: add a short text list under each EXE, for example a `<details><summary>Matched and partial functions (11)</summary><ul>…</ul></details>` built from `_function_title` for every non-unmatched function. That needs no script, works without a mouse, and keeps the output deterministic.
2. **The mosaic is unreadable at phone width.** On a 375 px viewport the 1200x800 SVG (progress.py:715) scales by about 0.31. Unit labels at 11 px and legend text at 12 px end up near 3.5 px, and the legend is lost. Fix: inside `.mosaic`, let the SVG scroll horizontally on small screens (`.mosaic{overflow-x:auto}` with `.mosaic svg{min-width:48rem}` under the 40rem query), or move the legend out of the SVG into HTML, as STRIP_KEY already does.
3. **At current values the bar shows nothing.** At 0.0091% and 0.0035%, the `.bar span` width rounds to well under 1 px. The bar reads as "nothing done" and gives no sign of the 3+2 matches or 8+6 partials. Fix: put the function counts first in `_figures` ("3 of 1,553 functions matched, 8 partial; 0.0091% of code bytes"), or give a non-zero bar a 2 px minimum width (`min-width:2px` when the percent is above 0) so progress is visible. Keep the byte percentage as the stated metric.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)
- WARNING: The figures line (progress.py:1062-1065) leads with "0.0091% of code bytes". The headline number is the least readable one at this stage, and four decimal places look like noise. Leading with the function counts, or saying "under 0.01%", would read better. The definition stays the same either way.
- WARNING: STRIP_KEY (progress.py:998-1002) is emitted after both EXE sections (render_html line 1127), so readers meet the ticks before the legend that explains them. Move it above the first `.exe`, or under the first strip.
- WARNING: The `<title>` is "ReverseApoc progress" but the `<h1>` is "X-COM: Apocalypse (DOS) decompilation progress" (lines 971-972). A browser tab or a shared link shows the project codename, not the game. Consider "X-COM: Apocalypse decompilation progress — ReverseApoc".
- PASS: The "How it is measured" text (MEASURED, lines 1003-1019) is precise and honest. It says partials count for nothing, explains the uncovered filler as D-50 requires, says the runtime is excluded, and links the raw sources. It has no generic labels and no marketing tone.

### Pillar 2: Visuals (2/4)
- WARNING: At current progress the bar (`.bar`, 8 px, line 1042) is visually empty, and it carries no partial segment even though partials are tracked. The strip does the real visual work. The bar adds little until the percentage passes about 1%.
- WARNING: The mosaic is a fixed 1200x800 viewBox scaled to `width:100%` (lines 1053-1054). On a phone, unit labels (LABEL_FONT_SIZE 11) and the in-SVG legend (FONT_SIZE 12, LEGEND_CHAR spacing) shrink to about 3.4-3.7 px. That is decorative, not informative. Tablets fare a little better (about 0.6 scale, about 7 px).
- WARNING: The h1 has no visual focal point beyond its 1.75rem size. With two near-empty bars, the first screen is mostly text. This is acceptable for a status page, but the EXE sections would scan faster if the headline figure were larger (for example the matched-function count at 1.25rem).
- PASS: The strip's height cue (14 px versus 8 px, TICK_HEIGHT/TICK_SHORT) is a good non-colour channel. The strip has an aria-label holding its counts, and the decorative `<i>` elements in the key are `aria-hidden`.

### Pillar 3: Color (3/4)
- PASS: There is one token set (SURFACE/INK/SECONDARY_INK, plus DARK_* at line 983), dark mode is done through custom properties, and the inline mosaic follows the scheme through MOSAIC_PAINTS. The contrast measurements are written down at lines 979-982. The status hues pass the CVD check (D-50).
- WARNING: The bar (`#008300` on `#898781`) and the mosaic cells tell matched from unmatched only by hue. The code notes the two are 1.38:1 apart in luminance (line 993), and the strip compensates with height, but the bar and mosaic do not. Partial `#eda100` next to uncovered `#d8d6cf` is also close in luminance in light mode. Fix: give the bar track a lighter neutral (for example the uncovered grey), and/or outline matched cells in the mosaic.
- WARNING: The standalone `progress.svg` stays light-only by design (line 984). Anyone embedding it on a dark README sees a bright block. This was a known trade-off, noted here for completeness.
- Hardcoded colours: they are all centralised constants (TREEMAP_COLORS line 709, surfaces lines 718 and 983). There are no stray literals in the CSS builder.

### Pillar 4: Typography (4/4)
- Sizes: h1 1.75rem, h2 1.125rem, body 1rem, meta/key/caption/figures .875rem, SVG 12/11 px. That is five steps, and the steps are clear.
- Weights: 700 (h1), 600 (h2), 400, and bold for the SVG heading. Three in total, which is acceptable.
- Body text keeps `max-width:70ch` and `line-height:1.5`, and the figures use `font-variant-numeric:tabular-nums`. The only typographic defect, the SVG text size on phones, is scored under Visuals.

### Pillar 5: Spacing (3/4)
- PASS: There is a consistent rem rhythm: .25/.5/.75/1/1.5/2/2.5/3rem, with fluid side padding `clamp(1rem,5vw,4rem)`, and the EXE grid stacks below 40rem.
- WARNING: `main{max-width:75rem}` has no `margin:0 auto` (line 1031), so on monitors wider than about 1300 px the content hugs the left edge and leaves a large empty right gutter. This may be intended, but it reads as unfinished on a wide screen.
- WARNING: The px tick geometry (2/1/3/8/14 px) is outside the rem scale. That is fine at 1x, but it does not grow with the user's font size, so ticks stay tiny at 200% text zoom.
- Minor: on desktop the `8rem` heading column can wrap "UFO2P.EXE"-style labels if they grow. They do not today.

### Pillar 6: Experience Design (2/4)
- WARNING (the main one): Every per-function detail sits in `title` attributes: tick `<i title>` (line 1075) and SVG `<title>` on rects (line 828). The partial-function best score, the headline feature of 06-24/06-27, cannot be reached on touch devices, cannot be focused by keyboard (ticks are not focusable, by design with no script), and is hidden from screen readers because the strip container is `role="img"` (line 1087), which flattens its children. The owner tested tooltips on a phone in UAT, but long-press `title` support varies by browser and should not be relied on.
- WARNING: Hitting a 2x14 px tick on desktop takes pixel-precise hovering. A 1 px gap between ticks makes neighbouring functions easy to mis-hit.
- WARNING: A stale `build/progress-page/progress.html` sits next to `index.html`, even though the owner ruled out a second copy (line 967-969). Check that the Pages workflow writes to a clean directory, so the stale file is never published.
- PASS: No script and no external requests. Links have a `:focus-visible` outline. The `lang`, viewport and color-scheme meta are set. `aria-labelledby` ties each section to its heading. The output is deterministic.
- An empty state (zero functions) is handled in progress.json (`measurement: None`, line 613). The page path for a zero-function EXE was not checked visually.

---

## Files Audited
- C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/tools/progress.py (lines 700-1170: mosaic, page CSS, render_html)
- C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/build/progress-page/index.html (figures and key placement)
- C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/.planning/phases/06-reporting-and-agent-pilot/06-27-SUMMARY.md, 06-CONTEXT.md (D-26, D-50)
