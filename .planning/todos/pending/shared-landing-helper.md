---
title: One landing helper for flags approve and twins
created: 2026-11-18
area: twins
source: batch 2026-11-18 worker reports
---

# One landing helper for flags approve and twins

U13 (batch 2026-11-18): twins reuses flags._Approver's private helpers. Factor a shared landing helper (write unit, container lint, gate --attempts 0, status, one commit with a trailer, restore on failure).
