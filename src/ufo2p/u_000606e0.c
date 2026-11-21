/*
 * src/ufo2p/u_000606e0.c: translation unit u_000606e0 of UFO2P.EXE, 0x000606E0..0x00060C50 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000606e0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000606E0);
INCLUDE_ASM(func_000607A0);
INCLUDE_ASM(func_00060860);
INCLUDE_ASM(func_00060930);
extern int *D_0017FB4C;
extern unsigned char D_000D9443[];
extern int D_000D4CBC;
extern void func_00060C80(int code);
extern void func_00010300(void);
extern void exit(int code);

int func_00060BD0(int arg)
{
    int result;
    int found;
    int offset;
    unsigned char value;

    result = 0;
    if (arg == 1) {
        if (D_0017FB4C[2] < -5000)
            result = 1;
    } else {
        value = D_000D9443[0];
        found = 0;
        offset = 0;
        if (value) {
hit:
            found = 1;
        } else {
            for (;;) {
                offset += 0x2be;
                if (offset >= 0x2be0)
                    break;
                if (D_000D9443[offset])
                    goto hit;
            }
        }
        if (found == 0)
            result = 2;
    }
    if (result) {
        func_00060C80(result);
        D_000D4CBC = 0x33;
        func_00010300();
        exit(D_000D4CBC);
    }
    return result;
}

struct unk_007E {
    /* 0x00 */ s16 f;
    /* 0x02 */ u8 pad_02[0x7C];
}; /* size: 0x7E */

extern struct unk_007E D_00128602[];

int func_00060BA0(int i)
{
    int r;

    r = 0;
    if (D_00128602[i].f != 0) r = 1;
    return r;
}
