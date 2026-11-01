/*
 * src/ufo2p/u_00089980.c: translation unit u_00089980 of UFO2P.EXE, 0x00089980..0x0008B750 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00089980`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 *
 * pager_screen_run is a modal paged screen: its first argument picks a section, whose page
 * count is the table at 0x0012F9E8, and its second is the page, stepped by one either way
 * and wrapped to -1 past the last page. Page -1 is the section's first (index) page. The
 * matched functions below each open one section at that page and clear the screen's
 * pending action pager_screen_action once it returns.
 */
#include "common.h"

/* page -1: 0x00089980 wraps the page to -1 when it reaches the section's page count */
#define PAGER_INDEX_PAGE -1

INCLUDE_ASM(pager_screen_run);
INCLUDE_ASM(func_0008A0C0);
INCLUDE_ASM(func_0008A1E0);
INCLUDE_ASM(func_0008A420);
INCLUDE_ASM(func_0008A900);
INCLUDE_ASM(func_0008AAF0);
INCLUDE_ASM(func_0008B4A0);
INCLUDE_ASM(func_0008B530);

/* void: EAX only holds the callee's result at ret; the callers decide. */
void pager_screen_run(int section, int page);

/* pager_open_section_4: open paged screen section 4
 * Address: UFO2P.EXE 0x0008A100
 * Evidence: call: calls 0x00089980 with section 4 and page -1, then clears 0x001A714C
 * void: EAX only holds pager_screen_run's result at ret; the callers decide.
 */
void pager_open_section_4(void)
{
    extern short pager_screen_action;

    pager_screen_run(4, PAGER_INDEX_PAGE); /* lit: section number; no string names the sections */
    pager_screen_action = 0;
}

/* pager_open_section_6: open paged screen section 6
 * Address: UFO2P.EXE 0x0008A120
 * Evidence: call: calls 0x00089980 with section 6 and page -1, then clears 0x001A714C
 * void: EAX only holds pager_screen_run's result at ret; the callers decide.
 */
void pager_open_section_6(void)
{
    extern short pager_screen_action;

    pager_screen_run(6, PAGER_INDEX_PAGE); /* lit: section number; no string names the sections */
    pager_screen_action = 0;
}

/* pager_open_section_8: open paged screen section 8
 * Address: UFO2P.EXE 0x0008A140
 * Evidence: call: calls 0x00089980 with section 8 and page -1, then clears 0x001A714C
 * void: EAX only holds pager_screen_run's result at ret; the callers decide.
 */
void pager_open_section_8(void)
{
    extern short pager_screen_action;

    pager_screen_run(8, PAGER_INDEX_PAGE); /* lit: section number; no string names the sections */
    pager_screen_action = 0;
}

/* pager_open_section_9: open paged screen section 9
 * Address: UFO2P.EXE 0x0008A160
 * Evidence: call: calls 0x00089980 with section 9 and page -1, then clears 0x001A714C
 * void: EAX only holds pager_screen_run's result at ret; the callers decide.
 */
void pager_open_section_9(void)
{
    extern short pager_screen_action;

    pager_screen_run(9, PAGER_INDEX_PAGE); /* lit: section number; no string names the sections */
    pager_screen_action = 0;
}

/* pager_open_section_7: open paged screen section 7
 * Address: UFO2P.EXE 0x0008A180
 * Evidence: call: calls 0x00089980 with section 7 and page -1, then clears 0x001A714C
 * void: EAX only holds pager_screen_run's result at ret; the callers decide.
 */
void pager_open_section_7(void)
{
    extern short pager_screen_action;

    pager_screen_run(7, PAGER_INDEX_PAGE); /* lit: section number; no string names the sections */
    pager_screen_action = 0;
}

/* pager_open_section_1: open paged screen section 1
 * Address: UFO2P.EXE 0x0008A1A0
 * Evidence: call: calls 0x00089980 with section 1 and page -1, then clears 0x001A714C
 * void: EAX only holds pager_screen_run's result at ret; the callers decide.
 */
void pager_open_section_1(void)
{
    extern short pager_screen_action;

    pager_screen_run(1, PAGER_INDEX_PAGE);
    pager_screen_action = 0;
}

/* pager_open_section_2: open paged screen section 2
 * Address: UFO2P.EXE 0x0008A1C0
 * Evidence: call: calls 0x00089980 with section 2 and page -1, then clears 0x001A714C
 * void: EAX only holds pager_screen_run's result at ret; the callers decide.
 */
void pager_open_section_2(void)
{
    extern short pager_screen_action;

    pager_screen_run(2, PAGER_INDEX_PAGE); /* lit: section number; no string names the sections */
    pager_screen_action = 0;
}

extern short pager_screen_action;

/* pager_open_section_3: open paged screen section 3
 * Address: UFO2P.EXE 0x0008A0E0
 * Evidence: call: calls 0x00089980 with section 3 and page -1, then clears 0x001A714C
 * void: EAX only holds pager_screen_run's result at ret; the callers decide.
 */
void pager_open_section_3(void)
{
    pager_screen_run(3, PAGER_INDEX_PAGE); /* lit: section number; no string names the sections */
    pager_screen_action = 0;
}
