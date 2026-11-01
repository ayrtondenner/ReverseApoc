/*
 * src/ufo2p/u_0005db20.c: translation unit u_0005db20 of UFO2P.EXE, 0x0005DB20..0x0005E5E0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0005db20`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0005DB20);
INCLUDE_ASM(func_0005DB80);
INCLUDE_ASM(func_0005DC30);
INCLUDE_ASM(func_0005DCC0);
INCLUDE_ASM(func_0005DEF0);
INCLUDE_ASM(func_0005E140);
INCLUDE_ASM(func_0005E230);
INCLUDE_ASM(func_0005E3C0);
INCLUDE_ASM(func_0005E430);
INCLUDE_ASM(func_0005E500);
INCLUDE_ASM(func_0005E550);

struct unk_015E {
    /* 0x000 */ s16 id;
    /* 0x002 */ u8 data[0x15C];
}; /* size: 0x15E */

extern struct unk_015E D_00179A5C[];

int rec15e_table_any_used(void)
{
    s16 i;
    int r;
    struct unk_015E *p;

    p = D_00179A5C;
    r = 0;
    i = 0;
    do {
        if (p->id != -1) {
            r = 1;
            break;
        }
        i++;
        p++;
    } while (i < 50);
    return r;
}
