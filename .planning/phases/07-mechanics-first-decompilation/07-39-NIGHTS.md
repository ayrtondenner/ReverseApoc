# 07-39 night log

One entry per owner-started night, for the plan's SUMMARY when it closes. Matches are proven by commit and by the end checks, not by console lines.

## Stall rule

Two consecutive ENDED nights with the Tier 1 matched count unchanged stop the loop. A STOPPED night neither counts toward the rule nor resets it.

Count so far: 0 flat nights.

## Run 20261107-030004 (2026-11-07)

`uv run reverseapoc drive --workers 10 --max-sessions 100`, all on `claude-opus-5-5`.

**Outcome.** STOPPED `tool` after 57 of 100 sessions and 1 h 54 min. Nine more sessions were cut off at the stop and are not counted.

**Cause.** `func_00099830` attempt 3 hit the 1,800 s limit during a check. Its `--rm` container was already being removed by docker when the driver's `docker rm -f` arrived, and that exit 1 stopped the night. Docker's message was not kept, so the cause rests on a probe: 1 of 40 throwaway `--rm` containers gave exit 1 with `removal of container ... is already in progress`, and a container already gone gives exit 0. The driver now treats that refusal as no failure once the container is gone.

**Checks run by hand.** A stopped night skips the end checks, so they ran on the night's tree: `ninja verify` exit 0, both EXEs at their SHA-1, and `gate --all` exit 0.

**Tier 1.** 102 matched before, 114 after, of 943 members. All 12 matches are Tier 1.

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
- Regated, waiting for the owner's `flags approve`: F-0062, F-0063 and F-0067. Their evidence includes a cut-off session with no attempt record, which `flags approve` refused until `ed9081d8` let it read the model from the transcript. They were regated again on the new `cflags.txt`.
- Failed regate on a compile error: F-0013, F-0028, F-0029.
- Skipped: `func_000A6EA0`, because F-0047 stays open for its unit.
