/*
 * src/ufo2p/u_000aa5f0.c: translation unit u_000aa5f0 of UFO2P.EXE, 0x000AA5F0..0x000AB080 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000aa5f0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000AA5F0);
INCLUDE_ASM(func_000AA690);
INCLUDE_ASM(func_000AAD30);

extern int list_screen_is_closed;

/* list_screen_on_close: button callback that closes the list screen
 * The screen loop at 0x000A99D0 clears this flag, then redraws until it is set
 * (or a key test passes) and returns the selection held in D_0012F4CC.
 * Address: UFO2P.EXE 0x000AAD20
 * Evidence: call: 0x000A96B0 passes it as the callback of the button it builds with 0x0002E640 at 0x000A99A8
 * Evidence: call: 0x000A99D0 clears list_screen_is_closed at 0x000A99E1 and leaves its loop at 0x000A9AA2 when it is set
 */
void list_screen_on_close(void)
{
    list_screen_is_closed = 1;
}
