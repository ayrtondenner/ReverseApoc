---
title: Record an environment digest in every run record
created: 2026-11-18
area: driver
files: tools/reverseapoc/driver.py, tools/reverseapoc/stats.py
source: literature mining of 2026-11-18 (docs/research/notes-ideas-tooling-reproducibility.md #1)
---

# Record an environment digest in every run record

**Why.** EdgeBench's OpenTTD score could not be reproduced partly because the work image differed; our run records name CLI versions but not the tool commit, image ID, or the hashes of cflags, watcom.toml, prices, quota and skills.

**Do.** Add an `environment` object to the run STARTED record: repo commit, image digest, config and skill hashes, each arm's CLI version.

**Done when.** validate_record accepts it; stats --run prints it; two runs with different skills show different digests.

**Effort / value.** S / high. Evidence and sources: docs/research/notes-ideas-tooling-reproducibility.md #1.

## Resolution (2026-11-18)

Done in batch 2026-11-18 (U2): STARTED records carry an environment digest; `stats --run` prints it.
