/*
 * src/ufo2p/u_00029900.c: translation unit u_00029900 of UFO2P.EXE, 0x00029900..0x0002B810 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00029900`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"


int sys_delay(int);

int func_00029900(void)
{
    return sys_delay(12);
}

INCLUDE_ASM(func_00029910);
INCLUDE_ASM(func_0002A250);
INCLUDE_ASM(func_0002AD90);
INCLUDE_ASM(func_0002AF40);
INCLUDE_ASM(func_0002B320);

extern int ui_screen_exit_requested;

/* ui_request_screen_exit: button callback requesting the screen exit
 * Sets the exit flag ui_screen_exit_requested; the screen loop in func_0002A250 clears it on entry and
 * leaves the loop once it is nonzero. void: EAX is not set before ret.
 * Address: UFO2P.EXE 0x0002A220
 * Evidence: call: 0x0002A250 pushes it as a callback to 0x0002E640 at 0x0002A3B7 and 0x0002A404
 * Evidence: call: 0x0002A250 tests the flag at 0x0002AD13 to end its loop
 */
void ui_request_screen_exit(void)
{
    ui_screen_exit_requested = 1;
}
