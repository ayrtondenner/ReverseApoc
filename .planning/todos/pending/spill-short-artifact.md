---
title: Re-prove the M5 'short beside a short moves with its declaration' claim
created: 2026-11-18
area: search
source: batch 2026-11-18 worker reports
---

# Re-prove the M5 'short beside a short moves with its declaration' claim

U12 (batch 2026-11-18) found that pr_spill_short and pr_spill_short_rev differ only in trailing alignment filler because pr_spill_short_rev is the probe's last function. Appending frames after it made both compile identically. search._readable's refusal built on M5 is on the safe side, but the claim is unproven: add frames that test it away from the file's end.
