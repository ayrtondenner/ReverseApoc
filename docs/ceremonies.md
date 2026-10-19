# Ceremonies

Byte-matching code is not the end goal on its own: the source should also read like code a 1997 developer could have written, and it should explain itself to OpenApoc readers. These are the review, simplify, security and comment passes we run after real progress, and the rules for where each one may act.

## The one rule: matched C keeps its shape

Matched C is frozen by the binary. Any change of shape changes what Watcom generates: register allocation, stack-slot order (declaration order decides it), loop layout, branch order, which temporaries get spilled. A "simpler" function that behaves the same will almost always compile to different bytes and break the match.

So on matched functions the only allowed edits are:

- comments;
- names of locals, parameters, functions, globals and types (renaming does not change codegen);
- whitespace and formatting that the build proves neutral (rebuild and compare after formatting).

Anything else, including "harmless" cleanups, goes through the full loop again and must still produce identical bytes. See [coding-style.md](coding-style.md#what-conflicts-with-match-the-original).

## Which pass runs where

| Pass | Python tooling (`tools/`, `tests/`, `configure.py`) | Matched C (`src/`, `include/`) |
|---|---|---|
| `/code-review` (built-in, local diff) | Yes | Comments, names and docs only; restructuring findings are not applied |
| `/code-review:code-review` (plugin, PR-only via `gh`) | Yes, once work flows through PRs | Same rule as above |
| `/simplify` and the `code-simplifier` agent | Yes | Never |
| `/security-review` (built-in) | Occasionally: Docker, CI, scripts that read user-supplied files | No (offline 1997 game code) |
| `security-guidance` plugin (hooks, LLM review on Stop) | Runs automatically; installed at project scope by the owner's choice | Its web-vulnerability focus is noise here; ignore its suggestions on matched code |
| `/verify` (built-in) | Yes, with a recorded recipe that builds and runs pytest | Yes, where "verify" means rebuild and whole-EXE SHA-1 identical |
| `ruff` (lint and format) | Yes | n/a |
| `clang-format` | n/a | C only, with pragma masking (below) |
| Comment pass | Docstrings as needed | Yes: the main ceremony for matched code |

Notes:

- The built-in `/code-review` and the plugin's `/code-review:code-review` are different commands; the plugin version needs a pull request.
- `security-guidance` runs an LLM review hook every turn, which costs tokens. The owner may disable it if the cost is not worth it.

### clang-format on C

clang-format rewrites the inside of `#pragma aux` (`parm [eax]` becomes `parm[eax]`), so following Theme Hospital we:

- mask every pragma, with its continuation lines, before formatting and restore it afterwards ([format.py](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/tools/format.py));
- set `SortIncludes: Never` (include order can matter) and `ReflowComments: false`;
- treat formatting as build-neutral only once proven: format, rebuild, compare. "Formatting must never change the build."

## When to run them

- **After a batch of matches** (or the end of a plan inside a phase): the comment pass on the new functions, `/code-review` on the diff, rebuild and compare.
- **After tooling changes:** `/code-review`, `/simplify`, ruff, pytest; `/security-review` when Docker, CI or file-reading code changed.
- **At the end of a phase**, before `/gsd-verify-work`: `/claude-md-management:revise-claude-md` to capture what the session learned, then `/claude-md-management:claude-md-improver` to audit CLAUDE.md. Keep CLAUDE.md under 150 lines and move detail into `docs/`.

## Evaluated and skipped

| Tool | Why it is skipped |
|---|---|
| [thermo-nuclear code quality review](https://github.com/cursor/plugins/blob/main/cursor-team-kit/skills/thermo-nuclear-code-quality-review/SKILL.md) | Its "code judo" restructuring breaks matches; TypeScript-flavoured examples; the repo has no licence, and it is not installable as a Claude plugin |
| [Ponytail](https://github.com/dietrichgebert/ponytail) | "Write less code" does not apply when the binary dictates the shape; overlaps superpowers |
| [pstack](https://github.com/backnotprop/pstack) | A third workflow system on top of GSD and superpowers; delegates code to Grok by default; some parts are Cursor-only. Its read-only `comment-sicko` reviewer is the one idea worth remembering |

## i-have-adhd

[i-have-adhd](https://github.com/ayghri/i-have-adhd) shapes chat output: lead with the next action, numbered steps, no preamble, small groups. Its SKILL.md has no rules for code. We use it for chat and apply the same spirit to explanatory comments (say what matters first, keep it short). It never decides code shape.
