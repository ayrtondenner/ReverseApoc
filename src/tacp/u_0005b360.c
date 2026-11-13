/*
 * src/tacp/u_0005b360.c: translation unit u_0005b360 of TACP.EXE, 0x0005B360..0x0005E340 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0005b360`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0005B360);
INCLUDE_ASM(func_0005B3A0);
INCLUDE_ASM(func_0005B6D0);
INCLUDE_ASM(func_0005B6E0);
INCLUDE_ASM(func_0005C640);
INCLUDE_ASM(func_0005CA10);
INCLUDE_ASM(func_0005CA80);
INCLUDE_ASM(func_0005CD00);
INCLUDE_ASM(func_0005CDD0);

struct unk_015E {
    /* 0x000 */ s16 id;
    /* 0x002 */ u8 data[0x15C];
}; /* size: 0x15E */

extern struct unk_015E D_0012241C[];

struct unk_015E *func_0005C9E0(void)
{
    struct unk_015E *p;
    s16 i;

    p = D_0012241C;
    i = 0;
    do {
        if (p->id == -1) {
            break;
        }
        i++;
        p++;
    } while (i < 50);
    if (i == 50) {
        p = 0;
    }
    return p;
}
