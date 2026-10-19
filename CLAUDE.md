# ReverseApoc

Byte-matching decompilation of X-COM Apocalypse (DOS, 1997; Watcom C 10.x; DOS/4GW LE executables
UFO2P.EXE and TACP.EXE) to document the original engine for OpenApoc. Not a port. AI assistance
(Claude Code) is used openly; every match is proven by byte comparison, never by the agent's word.

## Hard rules

- Never commit game files, disassembly, or build output: `orig/`, `asm/`, `build/`, `third_party/`
  are gitignored. Never modify `orig/`, the hash manifests under `config/`, or the build scripts to
  make a check pass. No secrets in tracked files or in `.env` (`.mcp.json` expands `${TAVILY_API_KEY}` from the user environment, set as a Windows user variable).
- The Watcom 10.x compiler and the game are user-supplied; they are never baked into the Docker image.
- A matched function is byte-identical and stays that way: no restructuring, no "modernizing",
  no inline assembly to force a match. Rules per path live in `.claude/rules/`.
- Claude Code is the only agent runtime here. Install skills as plugins at project scope.

## Commands

```
uv run reverseapoc ingest          # copy your EXEs into orig/ and verify hashes
uv run reverseapoc check-orig      # verify orig/ against config/targets.toml
uv run reverseapoc parse-le orig/UFO2P.EXE
uv run pytest -q && uv run ruff check .
docker compose build && docker compose run --rm test
```

## Done gate

Tooling: tests and ruff green, in the container too. Decompiled code (from Phase 2 on): the
rebuilt EXE is SHA-1 identical to the original and objdiff reports 100% for the function.

## Workflow

GSD is not committed: run `npx @opengsd/gsd-core@1.18.0 --claude --local` once per clone, then `/gsd-health`.
GSD owns milestones and phases (`/gsd-plan-phase N`, `/gsd-execute-phase N`, `/gsd-verify-work N`,
`/gsd-spike`); superpowers owns work inside a phase (brainstorming, TDD, verification). Milestone 1
roadmap: `docs/workflow.md`. Review passes and what they may touch: `docs/ceremonies.md`.

## Where to read more

- `docs/toolchain.md`: targets, LE layout, compiler evidence, what is in the container
- `docs/coding-style.md`, `docs/matching.md`, `docs/learnings.md`: C89/Watcom rules and what we learn
- `docs/tools.md`: every tool and skill with its Use/Skip/Later verdict and install status
- `docs/legal.md`: assets, licenses (tools/ is GPLv3), AI-use statement
- `docs/superpowers/specs/2026-10-19-reverseapoc-design.md` and `docs/research/`: the design and
  the research behind it
