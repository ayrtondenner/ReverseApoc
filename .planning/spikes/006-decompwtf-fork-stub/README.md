---
spike: 006
idea: reporting-and-agent-pilot
name: decompwtf-fork-stub
type: standard
validates: "Given the pinned decomp.wtf v0.10.6 source (MIT, tag commit eba4693c) and this repo's unit files, where a function not matched yet is the bare marker INCLUDE_ASM(func_X); and objdiff names it func_X_, when fork mode opens a clone of the repo and func_000A3980's known C is submitted through compile_and_diff, then the definition replaces the marker, is built by our configure.py and ninja, is scored by objdiff, and `check` still exits 0"
verdict: INVALIDATED
related: [005]
tags: [decomp.wtf, fork-mode, d-01, d-02]
---

# Spike 006: decomp.wtf v0.10.6 fork mode does not accept the repo's stub convention

This is the spike named in the Phase 6 roadmap entry and in D-01. Can decomp.wtf's fork mode, used
without patches, drive matching on this repo? The answer decides between decomp.wtf and the minimal
own agent layer for AGT-10 (D-02, D-03).

## What This Validates

D-01 asks for code evidence plus a half-day smoke run:

- **Code evidence**, from the pinned source read as text:
  - `forks/csource.py` `_stub` needs `"`, `/`, `,` or a space before the name.
  - Fork mode looks functions up by objdiff's linker name `func_X_`.
  - A definition that finds no stub is inserted by `_insert_in_order` (stub kept), so the
    marker and the definition share one unit, which our D-12 check refuses.
  - `_CHEAT` is applied only to what the agent submits.
- **Smoke run** in the WSL2 distro `ubuntu-recovered`:
  - install the pinned tarball;
  - open a clone of this repo in fork mode;
  - submit func_000A3980's C (from `src/ufo2p/u_000a34f0.c`) through `compile_and_diff`;
  - record what happens.

## Source

- Tarball: `https://github.com/i12bp8/decomp.wtf/archive/refs/tags/v0.10.6.tar.gz`
- sha256: `0eb7bddd809217222664509bd51c5ebc2be10864d361baeacb521cb49ce11b86`
- Extracted to the gitignored `build/spike006/src/decomp.wtf-0.10.6/`.

On the host the source is untrusted data, so both scripts read it with `Path.read_text` and
`ast.parse` only. Patterns are rebuilt from the f-strings' literal parts, and no decomp.wtf module
is imported or executed. decomp.wtf ran only inside WSL2, during this spike. Nothing from it is
tracked (docs/legal.md: never imported or vendored).

## Code evidence

`stub_regex.py SRC` (stdlib only) rebuilds `_stub`'s pattern from the f-string in
`forks/csource.py`. Output, kept in `build/spike006/stub_regex.out`:

```
PASS csource.py bare-marker INCLUDE_ASM(func_000A34F0); matched False (expect False)
PASS csource.py quoted-marker INCLUDE_ASM("x", func_000A34F0); matched True (expect True)
PASS csource.py char-class [\"/,\s] '"':True '/':True ',':True ' ':True '(':False
PASS csource.py repo-markers 12 markers under src/, 0 found by _stub []
ALL PASS
```

`linker_name.py SRC` reads every `.py` file of the package with ast. The finder pattern is located
structurally: it is the `re.compile` in the `else` branch of `find`'s `if "::" in name`. The
script cross-checks the result against our own `configure.py` (loaded by path) and
`reverseapoc.symbols`. Output, kept in `build/spike006/linker_name.out`:

```
PASS symbols.py linker-suffix func_000A3980 -> func_000A3980_
PASS forkengine.py names-symbol last spelling "out.append(meta.get('symbol') or fn['name'].split('@')[0])", stripping calls [], strip() without args True
PASS forkengine.py symbol-source symbol dicts [('sync', 'sym', "f['name']")]
PASS csource.py finder-linker-name find('func_000A3980_') on `int func_000A3980(void) {` matched False
PASS csource.py finder-c-name find('func_000A3980') on `int func_000A3980(void) {` matched True
PASS forkengine.py attempt-refuses if span is None: raise NetworkError(f'send the complete definition of {names[0]} (with its body)'
PASS forkengine.py cheat-sites [('_attempt', '_strip_comments(source)'), ('edit_file', '_strip_comments(new)')], 2 uses
PASS forkengine.py attempt-inserts old_span from self._find(before, ...) True, 1 `if old_span` branch, else calls _insert_in_order True
PASS forkengine.py insert-keeps-stub 3 returns, 3 keep all of `text` around `code`
PASS linker_name.py insert-control keep-check on `text[:span[0]] + code + '\n' + text[span[1]:]` accepted False
PASS package replace-unused csource.replace callers []
PASS configure.py check-refuses marker+definition -> ['func_000A3980 is both defined in C and marked INCLUDE_ASM']
PASS configure.py check-control definition only -> []
ALL PASS
```

How the insert claims work:

- `attempt-inserts`: `_attempt` takes `old_span` from `self._find(before, names)`, which runs on
  the unit file's text, and its `if old_span:` branch has an `else` that calls
  `_insert_in_order`.
- `insert-keeps-stub`: each of `_insert_in_order`'s 3 returns is a concatenation that holds
  `code` and either `text` whole or `text[:x]` followed by `text[x:]` with the same `x`. Only
  newlines are trimmed at the seam, so no part of the file, the stub included, is dropped. The
  check refuses any other shape.
- `insert-control`: a planted return that drops `text[span[0]:span[1]]` is refused by the same
  check, so the check can fail.
- `replace-unused`: nothing in the package calls `csource.replace`, so the claim rests on
  `_insert_in_order`, not on `replace`.

Each script was also run with `--plant`, which flips one expectation (`bare-marker` and
`finder-linker-name`). Each then printed `1 FAILED` and exited 1 (`build/spike006/plant.out`,
`plant_linker.out`), so both checkers can fail.

What this means for a submission, with the build working:

1. Fork mode takes the function's name from objdiff, `func_000A3980_`.
2. `_attempt` looks for `func_000A3980_(` in the submitted C. It does not find it, so it raises
   "send the complete definition of func_000A3980_" before writing anything.
3. Suppose the plain name were used instead. `csource.find` would then fall back to `_stub`, which
   does not see `INCLUDE_ASM(func_X);`. `_attempt` would then write the definition through
   `_insert_in_order`, with the stub kept. Marker and definition in one unit is what our D-12
   check refuses, so `check` would fail.
4. `_CHEAT` would not get in the way: it reads the submitted text only, so the `INCLUDE_ASM` lines
   already in the tree are not refused.

## Smoke run

The script is `build/spike006/smoke_wsl.sh` (gitignored, sha256
`8a50e8d18849f053346a63ada8c379ae111161ae0ae14fbf4267e8faca1d055a`). It:

- runs `uv tool install --force "decompnet @ https://github.com/i12bp8/decomp.wtf/archive/refs/tags/v0.10.6.tar.gz"`;
- clones `https://github.com/ayrtondenner/ReverseApoc.git` into `~/spike006`;
- runs a short driver with the tool's own Python. The driver follows the app's fork steps:
  `forks.clone`, `kind`, `needs`, `setup` and `check`, then the MCP tool handlers
  `claim_function` and `compile_and_diff` for `func_000A3980`, then `compile_and_diff` again for
  `func_000A3980_`. Every step runs even when the one before it failed.

It patches nothing and installs no ninja, wibo, objdiff-cli or Watcom tree (D-01, D-03).

The executor's worktree guard refuses every `wsl` call, so the orchestrator ran the script once
from the main session, with the owner's authorization, on 2026-10-24:

```
MSYS_NO_PATHCONV=1 wsl -d ubuntu-recovered -- bash -l /mnt/c/.../build/spike006/smoke_wsl.sh > build/spike006/smoke.log 2>&1
```

The exit status was 0. A first attempt without `MSYS_NO_PATHCONV=1` failed before the script
started: Git Bash rewrote the `/mnt/c` path.

The real failure, quoted verbatim from `build/spike006/smoke.log`:

```
decompnet 0.10.6
== clone
git clone exit 0
== driver
cloning /home/ayrton/spike006/ReverseApoc
cloned into /home/ayrton/spike006/workspace/reverseapoc (configure project)
STEP clone: OK reverseapoc
STEP kind: OK configure
STEP needs: OK {'what': 'your copy of the game', 'path': None, 'sha1': None, 'auto': False, 'help': 'This project has its own setup. Follow its README in a terminal, in the project folder; once its build has produced objdiff.json, click Check again.', 'kind': 'configure', 'versions': [], 'version': None, 'readme': ...
STEP setup: ERROR NetworkError: this project has its own setup: follow its README, then click Check again
STEP check: ERROR NetworkError: no objdiff.json yet. The project's build creates it (often `python configure.py` or `make`); see its README
STEP claim_function: OK error: no function 'func_000A3980' in 'reverseapoc'
STEP compile_and_diff: OK error: no function 'func_000A3980' in 'reverseapoc'
STEP compile_and_diff linker name: OK error: no function 'func_000A3980_' in 'reverseapoc'
driver exit 0
```

The `readme` value is cut here (`...`); it is the start of this repo's README.

So fork mode clones the repo and sees a `configure` project. It then stops at its own `setup`,
because the project is not one it can set up by itself (`auto: False`). `check` refuses because
there is no `objdiff.json`. This repo does not track one (it is gitignored). `configure.py` writes
it next to `build.ninja`, at the repo root, which is exactly where `check` looks
(`fp.root / "objdiff.json"`). So the file's location is not a problem; it was missing only because
no build ran in WSL2. No function row is ever registered, so `compile_and_diff` answers "no function". The C is never
written into the unit, never built and never scored.

### WSL2 tools

From the log's `== tools after install` block:

| Tool | In ubuntu-recovered |
|---|---|
| uv | present, `/home/ayrton/.local/bin/uv` |
| ninja | **MISSING** |
| wibo | **MISSING** |
| objdiff-cli | **MISSING** |
| claude | present, `/home/ayrton/.local/bin/claude` |
| git | present (the clone ran) |

The `== tools before install` block did not survive in the log. stdout and stderr went to one file
through `wsl`, and uv's progress output overwrote the start of the file, as did part of the `setup`
traceback. Whether uv was there before the run therefore cannot be read from this log.

D-01 expected claude to be missing in WSL2, but it is present. ninja, wibo and objdiff-cli are
missing, as D-01 said. Without them our build cannot run in WSL2, and per D-01 they were not
installed.

## Verdict

**INVALIDATED** (D-02), on D-02's "no build in WSL2" clause alone.

- VALIDATED needs unpatched v0.10.6 to put a definition in place of our marker, score it through
  our ninja and objdiff, and leave `check` at exit 0.
- The smoke run never reached a build: `setup` refused, `check` found no `objdiff.json`, and
  ninja, wibo and objdiff-cli are missing in WSL2. No build in WSL2 is one of D-02's INVALIDATED
  conditions, and the verdict rests on that.
- What the code evidence adds is not a verdict reason; it is input for Phase 7. With a working
  build, unpatched fork mode would still not pass:
  - the linker-name lookup (`func_X_` against `func_X(`) refuses the submission;
  - the stub regex misses `INCLUDE_ASM(func_X);`, so `_insert_in_order` would add the definition
    with the stub kept, a unit our D-12 check refuses.
- Those two fixes, the stub regex and the `name_` to `name` lookup, are exactly the patches D-02
  lists for PARTIAL. This spike did not write or size them, and D-03 forbids a patched decomp.wtf
  in Phase 6. Sizing them against D-02's "about 50 lines", together with a WSL2 build wrapper, is
  left for the Phase 7 re-evaluation (D-03).

PARTIAL is treated like INVALIDATED for the pilot. Phase 6 uses the own agent layer (D-03, D-04):
the driver, the hooks, the `watcom-decomp` skill, the context pack and direct CLI calls through a
Bash allowlist. decomp.wtf is re-evaluated for Phase 7 claims (DEC-02/DEC-06).

## Not covered here

- A patched decomp.wtf, or a WSL2 build of this repo. Both are excluded by D-01 and D-03.
- `decomp mcp` and the GUI. The driver calls the same `tools.call` handlers the MCP server
  dispatches to, without the stdio transport.
- Whether objdiff's report would carry a demangled name for `func_X_`. `_names` would try it
  first, but objdiff has no Watcom demangler, so no such name is expected.
