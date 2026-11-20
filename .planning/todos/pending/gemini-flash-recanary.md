---
title: Re-canary gemini-flash on the current agy after its quota group resets
created: 2026-11-20
area: driver
files: config/driver/backends.toml, build/driver/canary/gemini-flash.json
source: owner rulings of 2026-11-19 (agy-search-web-guard)
---

# gemini-flash has no canary on the current agy

**Why.** The 2026-11-19 network guard (quick 261119-bhm, 261119-adv) changed agy's session settings and
added the advisory search-web probe. gpt-oss and agy-opus-4-6 passed on agy 1.5.13 that day; gemini-flash
could not run, because agy's "Gemini models" weekly group was at 0% (reset about 2026-11-26). agy also
updates itself (1.5.11 -> 1.5.12 -> 1.5.13 within one day), and a night refuses an arm without a PASS for
the installed version.

**Do.** After the Gemini group resets, run `reverseapoc drive --canary --night-model gemini-flash
--allow-egress gemini-flash` through the launcher just before a night; record the result and the
search-web advisory. The owner approved this canary on 2026-11-19.

**Done when.** build/driver/canary/gemini-flash.json says PASS for the installed agy, or the failure is a
todo of its own.
