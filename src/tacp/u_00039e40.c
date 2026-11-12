/*
 * src/tacp/u_00039e40.c: translation unit u_00039e40 of TACP.EXE, 0x00039E40..0x00039F50 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00039e40`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00039E80);
INCLUDE_ASM(func_00039E90);

struct unk_0034 {
    /* 0x00 */ u8 pad_00[0x20];
    /* 0x20 */ s32 field_20;
    /* 0x24 */ u8 pad_24[0x10];
}; /* size: 0x34 */

extern struct unk_0034 D_001EC594[];
extern struct unk_0034 D_001ED294[];
extern int D_002CCA84;
extern int D_002CCA94;
extern int D_002CCAA4;

/* The array form makes p's init and both compares address constants (imm32 fixups), which
 * allocates zero to ebx and p to edx and leaves eax untouched, as in the matched ufo2p
 * func_0002F220(int a). The unused parameter and the return type are the callers' to decide. */
void func_00039E40(int a)
{
    struct unk_0034 *p;
    int zero;

    zero ^= zero;
    p = D_001EC594;
    D_002CCA84 = zero;
    D_002CCAA4 = zero;
    D_002CCA94 = zero;
    if (p < D_001ED294) {
        do {
            p++;
            p[-1].field_20 = 0;
        } while (p < D_001ED294);
    }
}
