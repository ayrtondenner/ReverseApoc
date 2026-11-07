# 07-39 night log

One entry per owner-started night, for the plan's SUMMARY when it closes. Matches are proven by commit and by the end checks, not by console lines.

## Stall rule

Two consecutive ENDED nights with the Tier 1 matched count unchanged stop the loop. A STOPPED night neither counts toward the rule nor resets it.

Count so far: 0 flat nights (run 20261107-170844 moved Tier 1 from 125 to 136).

## Run 20261107-030004 (2026-11-07)

`uv run reverseapoc drive --workers 10 --max-sessions 100`, all on `claude-opus-5-5`.

**Outcome.** STOPPED `tool` after 57 of 100 sessions and 1 h 54 min. Nine more sessions were cut off at the stop and are not counted.

**Cause.** `func_00099830` attempt 3 hit the 1,800 s limit during a check. Its `--rm` container was already being removed by docker when the driver's `docker rm -f` arrived, and that exit 1 stopped the night. Docker's message was not kept, so the cause rests on a probe: 1 of 40 throwaway `--rm` containers gave exit 1 with `removal of container ... is already in progress`, and a container already gone gives exit 0. The driver now treats that refusal as no failure once the container is gone.

**Checks run by hand.** A stopped night skips the end checks, so they ran on the night's tree: `ninja verify` exit 0, both EXEs at their SHA-1, and `gate --all` exit 0.

**Tier 1.** 102 matched before, 114 after, of 943 members. All 12 matches are Tier 1.

The 943 members above could not be reproduced on 2026-11-07: Tier 1 rows with role `member` in `config/mechanics-members.csv` number 1,269. That filter does give 114 matched at the night's end, so the matched count stands.

| Size | Sessions | Functions | Matched | Rate per session | Cost per session |
|---|---|---|---|---|---|
| Under 64 B | 18 | 8 | 3 | 16.7% | $0.95 |
| 64-255 B | 39 | 21 | 9 | 23.1% | $0.90 |
| 256 B and up | 0 | 0 | 0 | none | none |
| Total | 57 | 29 | 12 | 21.1% | $0.91 |

Recorded cost is $52.09, a lower bound: timed-out sessions are estimated from the stream, and the nine cut-off sessions are not counted. The weekly bar went from 9% to 15%.

**Match commits:** `ff623b90`, `469793cf`, `5d03b814`, `5c11bb0d`, `2e542b01`, `5d8432cc`, `98753bb6`, `90d76ce4`, `6afa6874`, `8647e5d2`, `546980c2`, `461a14a1`. Partial rows: `a0f685ed`.

**Skill and notes.**
- All 66 sessions ran `attempt asm`. 19 received a call-register note and 5 a case note. Whether any session acted on one cannot be told from what they wrote.
- 10 notes files name `slots only?`, and all 10 deny it. The phrase is new in the updated skill, so its text reached sessions, but no row reached the search.

**Sweep hits.** 16 functions had a sweep hit, and 2 of them later matched under the default rule. The other 14 are open: 9 at `-4r -oneatx -s -fpi`, 3 at `-4r -ox -s -fpi` and 2 at `-4r -ot -s -fpi`. A hit alone does not prove a row needs flags, as `func_00089060` showed. None has been proposed to the D-12 queue.

**D-12 queue (2026-11-07).** `flags propose --from-attempts 20261107-030004` added F-0058 to F-0068 and merged hits into F-0013, F-0028 and F-0029. The queue also picked up `func_00050D00`, a hit from a cut-off session, so 15 rows had open hits rather than 14.
- Landed by the owner: F-0058, F-0059, F-0060, F-0061, F-0064, F-0065, F-0066 and F-0068 (`07e3b528` to `16b497c5`).
- Landed by the owner after `ed9081d8`, which lets `flags approve` read a cut-off session's model from its transcript: F-0062, F-0063 and F-0067 (`0011d6bd` to `42cbe57e`). They were regated again on the new `cflags.txt` first.
- Tier 1 after all 11 landings: 125 matched.
- Failed regate on a compile error: F-0013, F-0028, F-0029.
- Skipped: `func_000A6EA0`, because F-0047 stays open for its unit.

## Run 20261107-170844 (2026-11-07)

`uv run reverseapoc drive --workers 10 --max-sessions 100`, all on `claude-opus-5-5`. It is the first night started from a Claude Code session, at the owner's request, after a clean dry run and `CANARY PASS` (run `ccsession-canary1`). The launcher removed every `CLAUDE*` variable and `GIT_EDITOR` first, so the sessions got a plain terminal's environment.

**Outcome.** ENDED `max sessions`: 100 sessions, 11 matched, in 4 h 23 min. No failed check, nothing uncommitted, nothing quarantined. It is the first night to run to its end since the docker removal fix (`e3c6648a`).

**End checks (the driver's).** `ninja verify` exit 0, both EXEs at their SHA-1, landed units 83 and 62. `gate --all` exit 0.

**Tier 1.** 125 matched before, 136 after. All 11 matches are Tier 1.

| Size | Sessions | Functions | Matched | Rate per session | Cost per session |
|---|---|---|---|---|---|
| Under 64 B | 5 | 3 | 3 | 60.0% | $0.82 |
| 64-255 B | 95 | 38 | 8 | 8.4% | $1.14 |
| 256 B and up | 0 | 0 | 0 | none | none |
| Total | 100 | 41 | 11 | 11.0% | $1.12 |

Recorded cost is $112.04. 41 of the 100 sessions hit the 1,800 s limit (9 of 57 the night before), and the rate per session at 64-255 B fell from 23.1% to 8.4%. The weekly bar was 17% at the start.

**Match commits:** `e2f21708`, `071b176c`, `3f813f8c`, `ab029123`, `5fa52871`, `9037a98b`, `9cd8851b`, `9476608c`, `95bad271`, `eac3eb43`, `541449d3`. Attempt log: `cfa21ed9`.

**Sweep hits.** 47 sessions logged one. 25 functions with a hit stay unmatched, waiting for `flags propose --from-attempts 20261107-170844`: 17 at `-4r -oneatx -s -fpi`, 5 at `-4r -ox -s -fpi` and 4 at `-4r -ot -s -fpi` (`func_00041660` hit two).
