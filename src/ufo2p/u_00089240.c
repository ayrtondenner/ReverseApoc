/*
 * src/ufo2p/u_00089240.c: translation unit u_00089240 of UFO2P.EXE, 0x00089240..0x00089980 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00089240`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 *
 * The rows 0x00089910..0x00089950 are five one-store setters of the 16-bit global
 * pager_screen_action (values 1 to 5); the 0x0008A0E0 family in u_00089980 resets it to 0.
 */
#include "common.h"

#define STATE_CODE_3 3
#define STATE_CODE_4 4
#define STATE_CODE_5 5

INCLUDE_ASM(func_00089240);
INCLUDE_ASM(func_00089360);
INCLUDE_ASM(func_00089910);
INCLUDE_ASM(func_00089920);
extern short pager_screen_action;

/* state_code_set_3: store state code 3
 * void: EAX is not set before ret.
 * Address: UFO2P.EXE 0x00089930
 * Evidence: call: stores 3 into the 16-bit global 0x001A714C; 0x00089910 and 0x00089920 store 1 and 2
 * Evidence: call: 0x0008A0E0 and its siblings in u_00089980 reset 0x001A714C to 0
 */
void state_code_set_3(void)
{
    pager_screen_action = STATE_CODE_3;
}

/* state_code_set_4: store state code 4
 * Defined right after state_code_set_3 so wcc386 emits the lea filler that ends its row.
 * Address: UFO2P.EXE 0x00089940
 * Evidence: call: stores 4 into the 16-bit global 0x001A714C, next to the setters for 1, 2, 3 and 5
 */
void state_code_set_4(void)
{
    pager_screen_action = STATE_CODE_4;
}

/* state_code_set_5: store state code 5
 * Address: UFO2P.EXE 0x00089950
 * Evidence: call: stores 5 into the 16-bit global 0x001A714C, the last of the setters for 1 to 5
 */
void state_code_set_5(void)
{
    pager_screen_action = STATE_CODE_5;
}
