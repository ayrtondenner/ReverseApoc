/*
 * src/ufo2p/u_00089980.c: translation unit u_00089980 of UFO2P.EXE, 0x00089980..0x0008B750 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00089980`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(pager_screen_run);
INCLUDE_ASM(func_0008A0C0);
INCLUDE_ASM(func_0008A1E0);
INCLUDE_ASM(func_0008A420);
INCLUDE_ASM(func_0008A900);
INCLUDE_ASM(func_0008AAF0);
INCLUDE_ASM(func_0008B4A0);
INCLUDE_ASM(func_0008B530);

/* void: EAX only holds the callee's result at ret; the callers decide. */
void pager_screen_run(int a, int b);

/* void: EAX only holds pager_screen_run's result at ret; the callers decide. */
void pager_open_section_4(void)
{
    extern short pager_screen_action;

    pager_screen_run(4, -1);
    pager_screen_action = 0;
}

/* void: EAX only holds pager_screen_run's result at ret; the callers decide. */
void pager_open_section_6(void)
{
    extern short pager_screen_action;

    pager_screen_run(6, -1);
    pager_screen_action = 0;
}

/* void: EAX only holds pager_screen_run's result at ret; the callers decide. */
void pager_open_section_8(void)
{
    extern short pager_screen_action;

    pager_screen_run(8, -1);
    pager_screen_action = 0;
}

/* void: EAX only holds pager_screen_run's result at ret; the callers decide. */
void func_0008A160(void)
{
    extern short pager_screen_action;

    pager_screen_run(9, -1);
    pager_screen_action = 0;
}

/* void: EAX only holds pager_screen_run's result at ret; the callers decide. */
void func_0008A180(void)
{
    extern short pager_screen_action;

    pager_screen_run(7, -1);
    pager_screen_action = 0;
}

/* void: EAX only holds pager_screen_run's result at ret; the callers decide. */
void func_0008A1A0(void)
{
    extern short pager_screen_action;

    pager_screen_run(1, -1);
    pager_screen_action = 0;
}

/* void: EAX only holds pager_screen_run's result at ret; the callers decide. */
void func_0008A1C0(void)
{
    extern short pager_screen_action;

    pager_screen_run(2, -1);
    pager_screen_action = 0;
}

extern short pager_screen_action;

/* void: EAX only holds pager_screen_run's result at ret; the callers decide. */
void pager_open_section_3(void)
{
    pager_screen_run(3, -1);
    pager_screen_action = 0;
}
