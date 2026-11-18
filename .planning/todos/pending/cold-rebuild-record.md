---
title: Publish a cold-rebuild verification record per verified commit
created: 2026-11-18
area: ci
files: .github/workflows/pages.yml, tools/progress.py
source: literature mining of 2026-11-18 (docs/research/notes-ideas-tooling-reproducibility.md #11)
---

# Publish a cold-rebuild verification record per verified commit

**Why.** CI proves each push, but no public record lists a from-scratch rebuild and its hashes per verified commit (isle's ReproBit).

**Do.** A CI job that rebuilds from a clean container and publishes the commit, image digest and both SHA-1s as a Pages artefact.

**Done when.** The record appears on the progress page for the latest verified commit.

**Effort / value.** M / med. Evidence and sources: docs/research/notes-ideas-tooling-reproducibility.md #11.
