/*
 * src/ufo2p/u_0005e5e0.c: translation unit u_0005e5e0 of UFO2P.EXE, 0x0005E5E0..0x0005E910 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0005e5e0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0005E610);
INCLUDE_ASM(func_0005E650);
INCLUDE_ASM(func_0005E690);

struct unk_0010 {
    /* 0x00 */ s16 id;
    /* 0x02 */ u8 pad_02[0x0E];
}; /* size: 0x10 */

extern struct unk_0010 D_0014D9F0[];

int func_0005E5E0(void)
{
    s16 i;
    int r;
    struct unk_0010 *p;

    p = D_0014D9F0;
    r = 0;
    i = 0;
    do {
        if (p->id == 0) {
            r = 1;
            break;
        }
        i++;
        p++;
    } while (i < 300);
    return r;
}
