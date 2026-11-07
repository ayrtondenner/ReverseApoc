/*
 * src/tacp/u_0004b8b0.c: translation unit u_0004b8b0 of TACP.EXE, 0x0004B8B0..0x0004C350 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0004b8b0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0004B8D0);
INCLUDE_ASM(func_0004C060);
INCLUDE_ASM(func_0004C1D0);
INCLUDE_ASM(func_0004C210);

struct unk_0056 {
    /* 0x00 */ u8 pad_00[0x47];
    /* 0x47 */ u8 unk_47;
    /* 0x48 */ u8 pad_48[0x0E];
}; /* size: 0x56 */

extern struct unk_0056 D_000F46D0[];

u8 *func_0001EB80(int a, int b, int c);
short func_0004C1D0(int a, int b, int c);

int func_0004C300(int a, int b, short c, short d, short e, short f)
{
    int result;
    struct unk_0056 *p;

    result = 0;
    p = &D_000F46D0[*func_0001EB80(d, e, c)];
    if (p->unk_47 == 0) {
        if (func_0004C1D0(d, e, f) > 0x19) {
            result = 1;
        }
    }
    return result;
}
