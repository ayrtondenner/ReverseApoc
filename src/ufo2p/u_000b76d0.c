/*
 * src/ufo2p/u_000b76d0.c: translation unit u_000b76d0 of UFO2P.EXE, 0x000B76D0..0x000B7740 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000b76d0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000B76D0);
INCLUDE_ASM(func_000B76F0);

#define KEY_FLAG_COUNT 100

extern unsigned char key_pressed_flags[];

/* key_take_first_pressed: take the first pressed key code
 * Scans the key flag bytes from code 1 up to 99, clearing each flag it reads, and returns
 * the first code whose flag was set (that flag is cleared too). Returns 0 when none is set;
 * entry 0 is never read.
 * Address: UFO2P.EXE 0x000B7710
 * Evidence: call: the text entry loop at 0x00029910 calls it each pass and turns the code into characters with 0x000B7870 or 0x000B78A0
 * Evidence: call: 0x00029910 first calls 0x000B76F0 for every code 0..99 before it starts reading keys
 */
int key_take_first_pressed(void)
{
    int code;
    int found;
    int flag;

    code = 1;
    found = 0;
    do {
        flag = key_pressed_flags[code];
        key_pressed_flags[code] = 0;
        if (flag != 0) {
            found = code;
            break;
        }
        code++;
    } while (code < KEY_FLAG_COUNT);
    return found;
}
