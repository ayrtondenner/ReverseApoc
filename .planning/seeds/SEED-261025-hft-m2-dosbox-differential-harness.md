---
id: SEED-261025-hft
status: dormant
planted: 2026-10-25
planted_during: Milestone 1, Phase 6 (Reporting and agent pilot)
trigger_when: "planning Milestone 2, before the #997 pilot spec needs dosbox-verified"
scope: medium
---

# SEED-261025-hft: DOSBox differential harness

## Why This Matters

A spec only reaches `dosbox-verified` on the SPEC-01 ladder when a test runs the original game and observes the predicted value. Phase 8's `speclint` only checks that a `dosbox-verified` claim names a test. Nothing in Milestone 1 builds that test runner. The #997 pilot spec ([[SEED-261025-os5]]) depends on it, and so does every later spec.

## Done Gate

From the original 7-12 proposal: the harness returns the same value twice from a fixed save, and fails when given a wrong prediction.

## When to Surface

**Trigger:** planning Milestone 2, sequenced before the pilot spec.

This is Track B, step B1 of the layout in [[SEED-261025-l4y]]. It starts on day one and needs nothing new from the decomp.

## Scope Estimate

**Medium.** Things to decide:
- Which emulator: DOSBox-X, DOSBox Staging, or 86Box.
- How to drive the game headless from a fixed save, and how to read a value out of it (a memory dump at a known address, or a save-file diff).
- How to keep it deterministic.

Avoid the host-folder `mount` drive type for long runs: its directory cache has the slot leak behind the "insert CD" bug ([[SEED-261025-hwp]]).

## Breadcrumbs

- `.planning/REQUIREMENTS.md`: SPEC-01 and SPEC-02 (the `dosbox-verified` rule).
- The Steam install ships DOSBox 0.72 with `mount c . -freesize 1024` and `imgmount d cd.iso -t iso` (checked locally on 2026-10-25).
