# GREEN retrieval test (new fresh agent, edited SKILL.md on qb-261119-bhp at e9c46cff, 2026-11-19)

- a) No: one shape (blocks and branches unchanged); line 212 calls it "a step within the same shape, not a new
  shape"; no other stop rule holds after 3 of 15, so "make the next C shape".
- b) Yes: six shapes (checks 1, 3, 5, 7, 9, 11), "at 256 B and up: six shapes".
- c) Yes: under 256 B, "three different C shapes leave objdiff below 100".
- d) Yes: "all 15 check runs are used".
- e) A check whose shape: line blocks or branches differ from the check before; the first check is the first shape;
  code length alone does not count.
- f) Six.

Verdict: GREEN (all six correct; a, e and f moved from RED).
