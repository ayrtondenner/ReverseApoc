/*
 * src/ufo2p/u_00066c50.c: translation unit u_00066c50 of UFO2P.EXE, 0x00066C50..0x00067DE0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00066c50`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00066C70);
INCLUDE_ASM(func_000670B0);
INCLUDE_ASM(func_00067550);
INCLUDE_ASM(func_00067870);
INCLUDE_ASM(func_00067930);

extern int confirm_is_accepted;

/* confirm_on_accept: button callback that accepts the dialog
 * The dialog at 0x00066780 clears this flag, then loops until it or the cancel
 * flag is set; when this one is set it goes on to the accept path.
 * Address: UFO2P.EXE 0x00066C50
 * Evidence: call: 0x00066780 passes it as the callback of the button it builds with 0x0002E640 at 0x0006690A
 * Evidence: call: 0x00066780 polls confirm_is_accepted at 0x00066A35 and takes the accept path at 0x00066A6C when it is set
 */
void confirm_on_accept(void)
{
    confirm_is_accepted = 1;
}

extern int confirm_is_cancelled;

/* confirm_on_cancel: button callback that cancels the dialog
 * Sets the flag that ends the wait loop of the dialog at 0x00066780 without
 * the accept path.
 * Address: UFO2P.EXE 0x00066C60
 * Evidence: call: 0x00066780 passes it as the callback of two buttons it builds with 0x0002E640 at 0x00066950 and 0x00066996
 * Evidence: call: 0x00066780 polls confirm_is_cancelled at 0x00066A3E only to leave its wait loop
 */
void confirm_on_cancel(void)
{
    confirm_is_cancelled = 1;
}
