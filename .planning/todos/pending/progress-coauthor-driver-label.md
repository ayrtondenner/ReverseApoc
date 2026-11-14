---
title: Progress timeline names a day's driver "9 co-authors" on flags-landing days
created: 2026-11-13
source: batch unit 2 report (progress-over-days chart)
---

# "9 co-authors: 2 matches" on 2026-11-11

`tools/progress.py`'s day summary groups match commits by their co-author set. Commits that land
held matches carry 7 to 10 `Co-Authored-By` trailers (every arm that matched), so the driver label
reads "9 co-authors: 2 matches" instead of naming a model. Decide the credit rule (the first
trailer, the `Matched-By` model, or one line per model) and fix it test first.
