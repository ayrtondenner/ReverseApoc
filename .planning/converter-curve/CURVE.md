# Converter follow-ups curve (batch 261107-qk9)

What the tools reach, point by point. The `measure_curve.py` beside this file writes it, and it
measures as the closed Phase 7.1 curve did. Point 7 is that curve's last summary row, copied
verbatim as the anchor. Point 8 is the baseline, measured after this harness merged, and each
later point is one follow-up item measured after its merge, with its plan cell naming the item's
quick id.

- **Seed and sample:** seed 20261103, and `SAMPLE.csv` is a byte copy of the Phase 7.1 sample,
  40 rows per bucket from 64 B up, fixed.
- **Cells:** the unit's committed rule and `-4r -oneatx -s -fpi`. A row is exact when either cell is.
- **Outcomes:** `exact`; `near`, compiled with a raw score of at least 90; `compiled`, with
  a lower score; `compile-failed`; `hole-draft`, a refused row that lifted with holes, which can
  never be exact; `refused`, the lifter raised `Unliftable` with holes too; `crash`, the lifter
  raised anything else. `matched` is a status, not an outcome, so matched rows get their own line.
- **Judge-exact:** every `exact` here is the judge's. A row can be judge-exact and still not land:
  tail merging and sibling regressions are the gate's to find.
- **A searched row:** the sample reads the draft's records and the winner's together, never a
  variant that did not win.
- **Move:** the Tier 1 number is converter-only and the sample runs every tool. A change in
  `exact` or `near` on either number is movement, of either sign. The Phase 7.1 stop rule was
  checked through point 3 only, so every point here reads `exempt (D-27)`. The rule:
  stop the phase after two plans in a row that move nothing.
- **Drift:** a row that lands between two points leaves the not-matched tables for the matched
  line, and a new cflags rule for a unit changes its committed cell. Compare points through the
  matched line and the `cflags sha256` cell, never through the not-matched tables alone.

| point | plan | head | cflags sha256 | result-used sha256 | tools | t1 exact | t1 near | s exact | s near | moved | flat streak | stop rule |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | 07.1-07 | 6a20ff0a919faf36e730e1b066d256f07b77caf9 | 5428038aff108e6fa8f545a1a8eda8e37a47827334797b2e12e00660688f4426 | ufo2p 71146929d2fd0ce9c9d0118d2ba55ffcfda8fde278c0bf602576f75f79441479 tacp fe42026431a063ddd9c74374ffa506bbdf0d621beff49c03915d9ac5b0cf1cb0 | converter, search, slots, classify | 21 | 14 | 1 | 0 | no | 0 | exempt (D-27) |
| 8 | 261107-qka | 6924bd5355d9c0d356335c85aaa77c2cc38e78aa | 14d0275ed305145592f46189576a1b6ea90f6808a6110fb85b0fc2ce26900b69 | ufo2p 71146929d2fd0ce9c9d0118d2ba55ffcfda8fde278c0bf602576f75f79441479 tacp fe42026431a063ddd9c74374ffa506bbdf0d621beff49c03915d9ac5b0cf1cb0 | converter, search, slots, classify | 18 | 12 | 1 | 0 | yes t1 exact -3, t1 near -2 | 0 | exempt (D-27) |
| 9 | 261107-qkb | 67c25cf16c85e1037474450ff51cae23802709a1 | 14d0275ed305145592f46189576a1b6ea90f6808a6110fb85b0fc2ce26900b69 | ufo2p 71146929d2fd0ce9c9d0118d2ba55ffcfda8fde278c0bf602576f75f79441479 tacp fe42026431a063ddd9c74374ffa506bbdf0d621beff49c03915d9ac5b0cf1cb0 | converter, search, slots, classify | 18 | 12 | 1 | 0 | no | 0 | exempt (D-27) |
| 10 | 261107-qkc | 19b2245fff59c6377fcb0c57a00c8525382b9ff5 | 14d0275ed305145592f46189576a1b6ea90f6808a6110fb85b0fc2ce26900b69 | ufo2p b58dd0d2c0ba8f96b20b15640733b8126d529262c8cdadd455216bef9b764996 tacp 31295a584f8f2008729341c22ddf43237bdcc7eafe07b4f2a14e65b0c70df73a | converter, search, slots, classify | 18 | 12 | 1 | 0 | no | 0 | exempt (D-27) |
| 11 | 261107-qkd | 370a652d078dcc2c9049f3c3d1525cec7a1de74b | 14d0275ed305145592f46189576a1b6ea90f6808a6110fb85b0fc2ce26900b69 | ufo2p eb5be9576e5a8d18a4d8b0bc2bdf04bade46792818a399916ac73f540c892b29 tacp 31295a584f8f2008729341c22ddf43237bdcc7eafe07b4f2a14e65b0c70df73a | converter, search, slots, classify | 18 | 12 | 1 | 0 | no | 0 | exempt (D-27) |
| 12 | 261107-qke | d865e156347cb08f4a11e7e9bfcc279387e2b03a | 14d0275ed305145592f46189576a1b6ea90f6808a6110fb85b0fc2ce26900b69 | ufo2p eb5be9576e5a8d18a4d8b0bc2bdf04bade46792818a399916ac73f540c892b29 tacp 31295a584f8f2008729341c22ddf43237bdcc7eafe07b4f2a14e65b0c70df73a | converter, search, slots, classify | 18 | 12 | 1 | 0 | no | 0 | exempt (D-27) |
| 13 | 261107-qkd | 47b09fa04c762960b32bfa0f9edab8805d7d1f69 | 14d0275ed305145592f46189576a1b6ea90f6808a6110fb85b0fc2ce26900b69 | ufo2p eb5be9576e5a8d18a4d8b0bc2bdf04bade46792818a399916ac73f540c892b29 tacp 31295a584f8f2008729341c22ddf43237bdcc7eafe07b4f2a14e65b0c70df73a | converter, search, slots, classify | 18 | 12 | 1 | 0 | no | 0 | exempt (D-27) |

## Point 8

Tier 1, 943 members, converter only:

| outcome | <64 | 64-255 | 256-1023 | >=1024 | all |
| --- | --- | --- | --- | --- | --- |
| exact | 15 | 3 | 0 | 0 | 18 |
| near | 4 | 8 | 0 | 0 | 12 |
| compiled | 37 | 212 | 155 | 18 | 422 |
| compile-failed | 0 | 11 | 6 | 5 | 22 |
| hole-draft | 15 | 53 | 153 | 87 | 308 |
| refused | 0 | 4 | 11 | 10 | 25 |
| crash | 0 | 0 | 0 | 0 | 0 |
| rows | 71 | 291 | 325 | 120 | 807 |

Matched rows (136): 72 exact, 55 compiled, 0 refused, 9 hole-draft.

Sample, 120 rows, tools: converter, search, slots, classify:

| outcome | <64 | 64-255 | 256-1023 | >=1024 | all |
| --- | --- | --- | --- | --- | --- |
| exact | 0 | 1 | 0 | 0 | 1 |
| near | 0 | 0 | 0 | 0 | 0 |
| compiled | 0 | 34 | 21 | 6 | 61 |
| compile-failed | 0 | 2 | 2 | 1 | 5 |
| hole-draft | 0 | 3 | 16 | 29 | 48 |
| refused | 0 | 0 | 1 | 4 | 5 |
| crash | 0 | 0 | 0 | 0 | 0 |
| rows | 0 | 40 | 40 | 40 | 120 |

`hole-draft` rows are refused rows that lifted with holes. They can never be exact and are never searched, so `refused` falls by them with no real gain. The reasons below count each such row's strict lift, so the retry lowers no first-refusal count.

Not-matched Tier 1 rows by class and route:

| class | converter | search | agent | all |
| --- | --- | --- | --- | --- |
| tail | 0 | 0 | 3 | 3 |
| slot | 0 | 0 | 0 | 0 |
| size | 2 | 0 | 659 | 661 |
| register | 2 | 0 | 1 | 3 |
| branch | 1 | 0 | 0 | 1 |
| mixed | 7 | 0 | 13 | 20 |
| none | 43 | 0 | 76 | 119 |
| rows | 55 | 0 | 752 | 807 |

Refusal reasons over the not-matched Tier 1 rows:

| reason | rows |
| --- | --- |
| op: cdq | 125 |
| call: stack-convention or odd callee name | 30 |
| pop: value not pushed in the block | 18 |
| op: movsd | 17 |
| call: stack arguments not pushed in the block | 15 |
| reg: esp read before any write | 15 |
| jump: indirect (switch table) | 13 |
| call: result of a void callee is used | 10 |
| jcc: no flag source | 10 |
| call: target is not a row start | 9 |
| op: rep movsd | 8 |
| call: indirect | 7 |
| decode: row does not decode to its end | 7 |
| stack: slot read at two widths | 7 |
| op: fsqrt | 6 |
| frame: ebp frame | 4 |
| op: repne scasb | 4 |
| x87: stack live across a block end | 4 |
| op: sbb | 3 |
| reg: esi read before any write | 3 |
| stack: saved register slot | 3 |
| idiv: dividend is not a cdq of eax | 2 |
| op: fldln2 | 2 |
| op: fldz | 2 |
| op: fxch | 2 |
| op: cwd | 1 |
| op: enter | 1 |
| op: in | 1 |
| op: iretd | 1 |
| op: one-operand imul | 1 |
| stack: address outside the frame | 1 |
| stack: slot above the frame that is no parameter | 1 |

## Point 9

Tier 1, 943 members, converter only:

| outcome | <64 | 64-255 | 256-1023 | >=1024 | all |
| --- | --- | --- | --- | --- | --- |
| exact | 15 | 3 | 0 | 0 | 18 |
| near | 4 | 8 | 0 | 0 | 12 |
| compiled | 37 | 224 | 191 | 32 | 484 |
| compile-failed | 0 | 12 | 7 | 8 | 27 |
| hole-draft | 15 | 40 | 115 | 70 | 240 |
| refused | 0 | 4 | 12 | 10 | 26 |
| crash | 0 | 0 | 0 | 0 | 0 |
| rows | 71 | 291 | 325 | 120 | 807 |

Matched rows (136): 72 exact, 58 compiled, 0 refused, 6 hole-draft.

Sample, 120 rows, tools: converter, search, slots, classify:

| outcome | <64 | 64-255 | 256-1023 | >=1024 | all |
| --- | --- | --- | --- | --- | --- |
| exact | 0 | 1 | 0 | 0 | 1 |
| near | 0 | 0 | 0 | 0 | 0 |
| compiled | 0 | 34 | 25 | 12 | 71 |
| compile-failed | 0 | 2 | 2 | 4 | 8 |
| hole-draft | 0 | 3 | 12 | 20 | 35 |
| refused | 0 | 0 | 1 | 4 | 5 |
| crash | 0 | 0 | 0 | 0 | 0 |
| rows | 0 | 40 | 40 | 40 | 120 |

`hole-draft` rows are refused rows that lifted with holes. They can never be exact and are never searched, so `refused` falls by them with no real gain. The reasons below count each such row's strict lift, so the retry lowers no first-refusal count.

Not-matched Tier 1 rows by class and route:

| class | converter | search | agent | all |
| --- | --- | --- | --- | --- |
| tail | 0 | 0 | 3 | 3 |
| slot | 0 | 0 | 0 | 0 |
| size | 2 | 0 | 657 | 659 |
| register | 2 | 0 | 1 | 3 |
| branch | 1 | 0 | 0 | 1 |
| mixed | 7 | 0 | 14 | 21 |
| none | 44 | 0 | 76 | 120 |
| rows | 56 | 0 | 751 | 807 |

Refusal reasons over the not-matched Tier 1 rows:

| reason | rows |
| --- | --- |
| call: stack-convention or odd callee name | 32 |
| op: cdq | 31 |
| pop: value not pushed in the block | 20 |
| op: movsd | 18 |
| reg: esp read before any write | 18 |
| call: stack arguments not pushed in the block | 16 |
| jcc: no flag source | 15 |
| jump: indirect (switch table) | 13 |
| call: result of a void callee is used | 11 |
| call: indirect | 10 |
| call: target is not a row start | 9 |
| op: rep movsd | 9 |
| op: fsqrt | 8 |
| decode: row does not decode to its end | 7 |
| idiv: dividend is not a cdq of eax | 7 |
| stack: slot read at two widths | 7 |
| x87: stack live across a block end | 5 |
| frame: ebp frame | 4 |
| op: repne scasb | 4 |
| reg: esi read before any write | 3 |
| stack: saved register slot | 3 |
| op: fldln2 | 2 |
| op: fldz | 2 |
| op: fxch | 2 |
| op: movsw | 2 |
| stack: slot above the frame that is no parameter | 2 |
| op: cwd | 1 |
| op: enter | 1 |
| op: in | 1 |
| op: iretd | 1 |
| op: one-operand imul | 1 |
| stack: address outside the frame | 1 |

## Point 10

Tier 1, 943 members, converter only:

| outcome | <64 | 64-255 | 256-1023 | >=1024 | all |
| --- | --- | --- | --- | --- | --- |
| exact | 15 | 3 | 0 | 0 | 18 |
| near | 4 | 8 | 0 | 0 | 12 |
| compiled | 37 | 237 | 198 | 40 | 512 |
| compile-failed | 0 | 0 | 0 | 0 | 0 |
| hole-draft | 15 | 39 | 115 | 70 | 239 |
| refused | 0 | 4 | 12 | 10 | 26 |
| crash | 0 | 0 | 0 | 0 | 0 |
| rows | 71 | 291 | 325 | 120 | 807 |

Matched rows (136): 72 exact, 58 compiled, 0 refused, 6 hole-draft.

Sample, 120 rows, tools: converter, search, slots, classify:

| outcome | <64 | 64-255 | 256-1023 | >=1024 | all |
| --- | --- | --- | --- | --- | --- |
| exact | 0 | 1 | 0 | 0 | 1 |
| near | 0 | 0 | 0 | 0 | 0 |
| compiled | 0 | 36 | 27 | 16 | 79 |
| compile-failed | 0 | 0 | 0 | 0 | 0 |
| hole-draft | 0 | 3 | 12 | 20 | 35 |
| refused | 0 | 0 | 1 | 4 | 5 |
| crash | 0 | 0 | 0 | 0 | 0 |
| rows | 0 | 40 | 40 | 40 | 120 |

`hole-draft` rows are refused rows that lifted with holes. They can never be exact and are never searched, so `refused` falls by them with no real gain. The reasons below count each such row's strict lift, so the retry lowers no first-refusal count.

Not-matched Tier 1 rows by class and route:

| class | converter | search | agent | all |
| --- | --- | --- | --- | --- |
| tail | 0 | 0 | 3 | 3 |
| slot | 0 | 0 | 0 | 0 |
| size | 2 | 0 | 732 | 734 |
| register | 2 | 0 | 1 | 3 |
| branch | 1 | 0 | 0 | 1 |
| mixed | 7 | 0 | 14 | 21 |
| none | 44 | 0 | 1 | 45 |
| rows | 56 | 0 | 751 | 807 |

Refusal reasons over the not-matched Tier 1 rows:

| reason | rows |
| --- | --- |
| call: stack-convention or odd callee name | 32 |
| op: cdq | 30 |
| pop: value not pushed in the block | 20 |
| op: movsd | 18 |
| reg: esp read before any write | 18 |
| call: stack arguments not pushed in the block | 16 |
| jcc: no flag source | 15 |
| jump: indirect (switch table) | 13 |
| call: result of a void callee is used | 11 |
| call: indirect | 10 |
| call: target is not a row start | 9 |
| op: rep movsd | 9 |
| op: fsqrt | 8 |
| decode: row does not decode to its end | 7 |
| idiv: dividend is not a cdq of eax | 7 |
| stack: slot read at two widths | 7 |
| x87: stack live across a block end | 5 |
| frame: ebp frame | 4 |
| op: repne scasb | 4 |
| reg: esi read before any write | 3 |
| stack: saved register slot | 3 |
| op: fldln2 | 2 |
| op: fldz | 2 |
| op: fxch | 2 |
| op: movsw | 2 |
| stack: slot above the frame that is no parameter | 2 |
| op: cwd | 1 |
| op: enter | 1 |
| op: in | 1 |
| op: iretd | 1 |
| op: one-operand imul | 1 |
| stack: address outside the frame | 1 |

## Point 11

Tier 1, 943 members, converter only:

| outcome | <64 | 64-255 | 256-1023 | >=1024 | all |
| --- | --- | --- | --- | --- | --- |
| exact | 15 | 3 | 0 | 0 | 18 |
| near | 4 | 8 | 0 | 0 | 12 |
| compiled | 37 | 240 | 208 | 44 | 529 |
| compile-failed | 0 | 0 | 1 | 0 | 1 |
| hole-draft | 15 | 36 | 104 | 66 | 221 |
| refused | 0 | 4 | 12 | 10 | 26 |
| crash | 0 | 0 | 0 | 0 | 0 |
| rows | 71 | 291 | 325 | 120 | 807 |

Matched rows (136): 73 exact, 59 compiled, 0 refused, 4 hole-draft.

Sample, 120 rows, tools: converter, search, slots, classify:

| outcome | <64 | 64-255 | 256-1023 | >=1024 | all |
| --- | --- | --- | --- | --- | --- |
| exact | 0 | 1 | 0 | 0 | 1 |
| near | 0 | 0 | 0 | 0 | 0 |
| compiled | 0 | 36 | 28 | 17 | 81 |
| compile-failed | 0 | 0 | 0 | 0 | 0 |
| hole-draft | 0 | 3 | 11 | 19 | 33 |
| refused | 0 | 0 | 1 | 4 | 5 |
| crash | 0 | 0 | 0 | 0 | 0 |
| rows | 0 | 40 | 40 | 40 | 120 |

`hole-draft` rows are refused rows that lifted with holes. They can never be exact and are never searched, so `refused` falls by them with no real gain. The reasons below count each such row's strict lift, so the retry lowers no first-refusal count.

Not-matched Tier 1 rows by class and route:

| class | converter | search | agent | all |
| --- | --- | --- | --- | --- |
| tail | 0 | 0 | 3 | 3 |
| slot | 0 | 0 | 0 | 0 |
| size | 2 | 0 | 727 | 729 |
| register | 2 | 0 | 1 | 3 |
| branch | 1 | 0 | 0 | 1 |
| mixed | 7 | 0 | 14 | 21 |
| none | 44 | 0 | 6 | 50 |
| rows | 56 | 0 | 751 | 807 |

Refusal reasons over the not-matched Tier 1 rows:

| reason | rows |
| --- | --- |
| call: stack-convention or odd callee name | 43 |
| op: cdq | 31 |
| pop: value not pushed in the block | 23 |
| reg: esp read before any write | 21 |
| call: stack arguments not pushed in the block | 18 |
| call: result of a void callee is used | 15 |
| jcc: no flag source | 15 |
| jump: indirect (switch table) | 13 |
| call: indirect | 11 |
| call: target is not a row start | 9 |
| idiv: dividend is not a cdq of eax | 8 |
| stack: slot read at two widths | 8 |
| decode: row does not decode to its end | 7 |
| x87: stack live across a block end | 5 |
| frame: ebp frame | 4 |
| op: repne scasb | 3 |
| reg: esi read before any write | 3 |
| stack: saved register slot | 3 |
| stack: address outside the frame | 2 |
| stack: slot above the frame that is no parameter | 2 |
| op: cwd | 1 |
| op: enter | 1 |
| op: in | 1 |
| op: iretd | 1 |
| op: one-operand imul | 1 |

## Point 12

Tier 1, 943 members, converter only:

| outcome | <64 | 64-255 | 256-1023 | >=1024 | all |
| --- | --- | --- | --- | --- | --- |
| exact | 15 | 3 | 0 | 0 | 18 |
| near | 4 | 8 | 0 | 0 | 12 |
| compiled | 37 | 240 | 208 | 44 | 529 |
| compile-failed | 0 | 0 | 1 | 0 | 1 |
| hole-draft | 15 | 36 | 104 | 66 | 221 |
| refused | 0 | 4 | 12 | 10 | 26 |
| crash | 0 | 0 | 0 | 0 | 0 |
| rows | 71 | 291 | 325 | 120 | 807 |

Matched rows (136): 73 exact, 59 compiled, 0 refused, 4 hole-draft.

Sample, 120 rows, tools: converter, search, slots, classify:

| outcome | <64 | 64-255 | 256-1023 | >=1024 | all |
| --- | --- | --- | --- | --- | --- |
| exact | 0 | 1 | 0 | 0 | 1 |
| near | 0 | 0 | 0 | 0 | 0 |
| compiled | 0 | 36 | 28 | 17 | 81 |
| compile-failed | 0 | 0 | 0 | 0 | 0 |
| hole-draft | 0 | 3 | 11 | 19 | 33 |
| refused | 0 | 0 | 1 | 4 | 5 |
| crash | 0 | 0 | 0 | 0 | 0 |
| rows | 0 | 40 | 40 | 40 | 120 |

`hole-draft` rows are refused rows that lifted with holes. They can never be exact and are never searched, so `refused` falls by them with no real gain. The reasons below count each such row's strict lift, so the retry lowers no first-refusal count.

Not-matched Tier 1 rows by class and route:

| class | converter | search | agent | all |
| --- | --- | --- | --- | --- |
| tail | 0 | 0 | 3 | 3 |
| slot | 0 | 0 | 0 | 0 |
| size | 2 | 0 | 727 | 729 |
| register | 2 | 0 | 1 | 3 |
| branch | 1 | 0 | 0 | 1 |
| mixed | 7 | 0 | 14 | 21 |
| none | 44 | 0 | 6 | 50 |
| rows | 56 | 0 | 751 | 807 |

Refusal reasons over the not-matched Tier 1 rows:

| reason | rows |
| --- | --- |
| call: stack-convention or odd callee name | 43 |
| op: cdq | 31 |
| pop: value not pushed in the block | 23 |
| reg: esp read before any write | 21 |
| call: stack arguments not pushed in the block | 18 |
| call: result of a void callee is used | 15 |
| jcc: no flag source | 15 |
| jump: indirect (switch table) | 13 |
| call: indirect | 11 |
| call: target is not a row start | 9 |
| idiv: dividend is not a cdq of eax | 8 |
| stack: slot read at two widths | 8 |
| decode: row does not decode to its end | 7 |
| x87: stack live across a block end | 5 |
| frame: ebp frame | 4 |
| op: repne scasb | 3 |
| reg: esi read before any write | 3 |
| stack: saved register slot | 3 |
| stack: address outside the frame | 2 |
| stack: slot above the frame that is no parameter | 2 |
| op: cwd | 1 |
| op: enter | 1 |
| op: in | 1 |
| op: iretd | 1 |
| op: one-operand imul | 1 |

## Point 13

Tier 1, 943 members, converter only:

| outcome | <64 | 64-255 | 256-1023 | >=1024 | all |
| --- | --- | --- | --- | --- | --- |
| exact | 15 | 3 | 0 | 0 | 18 |
| near | 4 | 8 | 0 | 0 | 12 |
| compiled | 37 | 240 | 209 | 44 | 530 |
| compile-failed | 0 | 0 | 0 | 0 | 0 |
| hole-draft | 15 | 36 | 104 | 66 | 221 |
| refused | 0 | 4 | 12 | 10 | 26 |
| crash | 0 | 0 | 0 | 0 | 0 |
| rows | 71 | 291 | 325 | 120 | 807 |

Matched rows (136): 73 exact, 59 compiled, 0 refused, 4 hole-draft.

Sample, 120 rows, tools: converter, search, slots, classify:

| outcome | <64 | 64-255 | 256-1023 | >=1024 | all |
| --- | --- | --- | --- | --- | --- |
| exact | 0 | 1 | 0 | 0 | 1 |
| near | 0 | 0 | 0 | 0 | 0 |
| compiled | 0 | 36 | 28 | 17 | 81 |
| compile-failed | 0 | 0 | 0 | 0 | 0 |
| hole-draft | 0 | 3 | 11 | 19 | 33 |
| refused | 0 | 0 | 1 | 4 | 5 |
| crash | 0 | 0 | 0 | 0 | 0 |
| rows | 0 | 40 | 40 | 40 | 120 |

`hole-draft` rows are refused rows that lifted with holes. They can never be exact and are never searched, so `refused` falls by them with no real gain. The reasons below count each such row's strict lift, so the retry lowers no first-refusal count.

Not-matched Tier 1 rows by class and route:

| class | converter | search | agent | all |
| --- | --- | --- | --- | --- |
| tail | 0 | 0 | 3 | 3 |
| slot | 0 | 0 | 0 | 0 |
| size | 2 | 0 | 729 | 731 |
| register | 2 | 0 | 1 | 3 |
| branch | 1 | 0 | 0 | 1 |
| mixed | 7 | 0 | 14 | 21 |
| none | 44 | 0 | 4 | 48 |
| rows | 56 | 0 | 751 | 807 |

Refusal reasons over the not-matched Tier 1 rows:

| reason | rows |
| --- | --- |
| call: stack-convention or odd callee name | 43 |
| op: cdq | 31 |
| pop: value not pushed in the block | 23 |
| reg: esp read before any write | 21 |
| call: stack arguments not pushed in the block | 18 |
| call: result of a void callee is used | 15 |
| jcc: no flag source | 15 |
| jump: indirect (switch table) | 13 |
| call: indirect | 11 |
| call: target is not a row start | 9 |
| idiv: dividend is not a cdq of eax | 8 |
| stack: slot read at two widths | 8 |
| decode: row does not decode to its end | 7 |
| x87: stack live across a block end | 5 |
| frame: ebp frame | 4 |
| op: repne scasb | 3 |
| reg: esi read before any write | 3 |
| stack: saved register slot | 3 |
| stack: address outside the frame | 2 |
| stack: slot above the frame that is no parameter | 2 |
| op: cwd | 1 |
| op: enter | 1 |
| op: in | 1 |
| op: iretd | 1 |
| op: one-operand imul | 1 |

Open after point 13 (batch 261107-qk9): with the header prototype fix (`47b09fa0`), calls to a function an included header declares go through the header's prototype, but the lifter still passes its own agreed count and types. Outside the Tier 1 table this leaves 3 compile failures in the batch records: tacp 0x0008C110 and ufo2p 0x00014A30 (E1151, floor and memset called with another count) and ufo2p 0x00073EE0 (E1071, a parameter type). The fix is for `agreed_counts` to take the header's count and types for those names. tacp 0x00064050 (E1079) is older.
