/*
 * src/ufo2p/u_000b33a0.c: translation unit u_000b33a0 of UFO2P.EXE, 0x000B33A0..0x000B3400 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000b33a0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

struct unk_0276 {
    /* 0x000 */ s16 unk_000;
    /* 0x002 */ s16 unk_002;
    /* 0x004 */ u8 pad_004[0x106];
    /* 0x10A */ s16 unk_10A;
    /* 0x10C */ u8 pad_10C[0x20];
    /* 0x12C */ s16 unk_12C;
    /* 0x12E */ u8 pad_12E[0x148];
}; /* size: 0x276 */

extern struct unk_0276 D_00160FD8[];
extern char D_0016D4B8[];

int func_000B33A0(int arg0)
{
    struct unk_0276 *rec;
    int result;

    rec = D_00160FD8;
    result = -1;
    if (rec < (struct unk_0276 *)D_0016D4B8) {
        do {
            if ((int)rec->unk_002 != -1 && (int)rec->unk_10A == arg0 && rec->unk_12C == 0) {
                result = rec - D_00160FD8;
                break;
            }
            rec++;
        } while (rec < (struct unk_0276 *)D_0016D4B8);
    }
    return result;
}
