---
title: Correct the records of the F-0035 and F-0077 flags landings (owner's call)
created: 2026-11-20
area: flags
files: config/cflags-proposals.toml, config/ufo2p/status.csv, config/tacp/status.csv, src/ufo2p/u_00076240.c
source: review of a685ec0f (F-0035) and 33b91481 (F-0077), 2026-11-20 (findings 1-4)
---

# What the two landings recorded wrong

The bytes are right in both (the regate.json files show objdiff 100, reloc ok and 0 differing
bytes for every defined function, and the EXE SHA-1s are as expected). Only the records and one
source text are wrong. The tooling that wrote them is fixed by the 2026-11-20
`fix(flags): ...` commit (regate refresh, the matched-C refusal, landed-C co-authors). The
landed records were left as they are: correcting them is the owner's call.

## 1. F-0035 matched func_00077F00 but every record of the approval says it stays partial

- config/ufo2p/status.csv:293 has `func_00077F00 ... matched,100.00,2,...,2026-11-20`, written by
  a685ec0f's gate, which matches every function the unit defines.
- The same commit's message (subject "match func_00077EC0, func_00077ED0", body
  "sibling func_00077F00 partial 20.00"), the approve output, and config/cflags-proposals.toml:896
  and :898 (F-0035 `functions` and `siblings`) say F00 is partial at 20.00.
- The subject names EC0, which was already matched (b21bf435, 2026-11-02). It omits F00, which
  this commit matched. The feed's 142 -> 144 is ED0 plus F00.
- F00's C came from the 20261101 EC0 attempt-1 (claude-opus-5-5, cited as evidence), so the
  Co-Authored-By line is right.

## 2. F-0035 replaced the committed C of func_00077EC0, which was already matched

- src/ufo2p/u_00076240.c:20 and :29-32. Before a685ec0f:
  `extern char D_000F3DC8[]; ... *(signed char *)((D_000F3DC8)) = 1; return;`.
  After: `extern unsigned char D_000F3DC8; ... D_000F3DC8 = 1;`, the text of the 20261101
  attempt, written before EC0 matched.
- .claude/rules/src.md: never restructure a function that already matches. The bytes were
  re-proven, so objdiff stays 100%. A replay of the new approve check on a685ec0f^ and a685ec0f
  names exactly func_00077EC0 as changed.

## 3. F-0077 credits GPT-6 Astra, whose C did not land

- 33b91481's trailer `Co-Authored-By: GPT-6 Astra <noreply@openai.com>`.
- The landed src/tacp/u_000743a0.c is byte for byte the Opus attempt's checks/0003.c
  (build/driver/20261119-claude-claude-opus-5-5/tacp/func_000743A0/attempt-1). GPT-6 Astra's
  checks/0001.c (20261119-quota5-gpt-6-astra) is a different text. Its hit only added evidence.
- Ruling F33: the co-author is each model that wrote the candidate. A replay of the fixed
  `_hitting_attempts` credits only the Opus attempt.

## 4. status.csv `attempts` of the new rows is the max over all evidence

| Row | before | after | own hitting attempt (attempts.jsonl) |
|---|---|---|---|
| ufo2p func_00077ED0 (:292) | 3 | 2 | 20261119 attempt 1 |
| ufo2p func_00077F00 (:293) | 1 | 2 | none of its own; its C is the EC0 attempt-1's |
| tacp func_000743A0 (:239) | 3 | 1 | 20261119 attempt 1 |

The 2 is EC0's 20261101 attempt-2, whose C did not land. With the fix, `--attempts` is the max over
the attempts whose C landed: 1 for F-0035, 1 for F-0077. Per-function attempts are still open:
.planning/todos/pending/flags-per-function-attempts.md.

# Options (owner)

- A. Leave the history and add one records commit that states the facts:
  - the queue's F-0035 `functions` becomes [ED0, F00], `keeps` [EC0], and F00 leaves `siblings`;
  - optionally the status.csv `attempts` of ED0 and F00 becomes 1;
  - the commit message records findings 1, 3 and 4, so `git log` traces F00 to it.
  Nothing here changes bytes. The status.csv edit goes through gate or by hand, under the
  owner's ruling, because the file says "written by gate; do not edit".
- B. Restore EC0's committed text (finding 2). Put the pre-a685ec0f definition of func_00077EC0,
  and the `extern char D_000F3DC8[];` it reads, back into src/ufo2p/u_00076240.c. Then run
  `gate ufo2p/u_00076240` under the F-0035 rule.
  - If EC0 still matches, the matched text is the one by hand again. It must still be checked
    that ED0 and F00 compile with that extern.
  - If EC0 no longer matches under the new rule, keep the landed text and record the ruling here
    (the rule change required it).
- C. Keep 33b91481's trailer (history is not rewritten), and record in docs/learnings.md or the
  paper facts pack that F-0077's GPT-6 Astra credit is a duplicate hit, not landed C. This matters
  if stats or the paper count co-authors from trailers. Today stats classes from status.csv and
  attempts.jsonl only.
- D. Rewrite the unpushed commits (a685ec0f, 33b91481 and the 7 after them). This is possible
  only because they are not pushed yet. It costs re-running the done gate, and it is not
  recommended over A to C.

# Ruling questions

- Should `flags regate` keep the committed text of already-matched functions in the candidate
  (splice them in and re-prove under the new rule)? The alternative is the owner handling each
  case. Today approve refuses such a landing (fail closed), and nothing in the tool rebuilds the
  candidate.
- Should an independent duplicate hit with byte-identical C (two models, same text) be credited?
  The fix credits every attempt whose checks/NNNN.c defines the function exactly as landed, so
  identical texts are both credited.
