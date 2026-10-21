# Clean room

How ReverseApoc's knowledge reaches OpenApoc without the decompiled code. This is a description of
our practice, not legal advice; whether it holds up is untested, and OpenApoc's maintainers decide
what they accept.

## What OpenApoc asked for

OpenApoc follows "Clean Room" practice, so no code from the original game is in OpenApoc, and
reversed material is analysed to build their own solutions. Two messages in the OpenApoc Discord
(#general) set the bar:

- FilmBoy84, 2026-09-27: the project's rules, including clean room
  ([message](https://discord.com/channels/142798944970211328/142798944970211328/1553677306583711817)).
  The replies point to the clean-room audit of game-derived assets in
  [OpenApoc discussion #1644](https://github.com/OpenApoc/OpenApoc/discussions/1644).
- JonnyH, 2026-10-08: clean room *must* have different people doing the reverse engineering and
  documentation and then re-implementing from that documentation; the same person doing both is
  not clean room. He also cautions against going too deep along automated AI paths
  ([message](https://discord.com/channels/142798944970211328/142798944970211328/1557818449911226419)).

## Roles

| Role | Works in | Reads | Never reads |
|---|---|---|---|
| Spec author | ReverseApoc | matched C in `src/`, Ghidra, community sources | OpenApoc's code, when writing the spec |
| Reviewer | ReverseApoc | the spec, its cited addresses and sources | nothing excluded |
| Implementer | an OpenApoc fork | `specs/` and OpenApoc's own code | `src/`, `include/`, `asm/`, Ghidra projects |

- The implementer should be a different person from the spec author. An agent that implements
  runs in an OpenApoc checkout that has no access to this repository's `src/`.
- AI drafts specs; a human (the owner) reviews every spec before it is marked reviewed, and that
  review is recorded in the spec.

## What crosses over

Only `specs/`: one spec per mechanic, in the OpenSpec format (requirements with SHALL/MUST, scenarios
with WHEN/THEN), plus constants, formulas, timings, function addresses as references, evidence and
dated sources. No C code, no text copied from `src/`, no game bytes. `reverseapoc speclint`
(Phase 8) checks this. The specs are CC0-1.0, see [legal.md](legal.md#specs-and-clean-room).

## Conduct

- No contact with OpenApoc about the specs during Milestone 1 (owner decision 2026-10-21).
- After that, ask the maintainers first: whether they want decomp-derived specs, in what format,
  and whether and at what pace they take AI-assisted pull requests. No flood of agent PRs.
- Corrections to community wikis found through the decomp are offered back in our own words.
