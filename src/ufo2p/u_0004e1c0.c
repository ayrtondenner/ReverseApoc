/*
 * src/ufo2p/u_0004e1c0.c: translation unit u_0004e1c0 of UFO2P.EXE, 0x0004E1C0..0x0004E6B0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0004e1c0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0004E1C0);
INCLUDE_ASM(func_0004E3B0);
INCLUDE_ASM(func_0004E420);
INCLUDE_ASM(func_0004E4B0);

struct unk_0175 {
    /* 0x00 */ u8 pad_00[0x02];
    /* 0x02 */ s16 x_02;
    /* 0x04 */ u8 pad_04[0x106];
    /* 0x10A */ s16 x_10a;
    /* 0x10C */ u8 pad_10c[0x20];
    /* 0x12C */ s16 x_12c;
    /* 0x12E */ u8 pad_12e[0x46];
    /* 0x174 */ u8 x_174;
}; /* size: not read, at least 0x175 */

extern s32 D_00182AD4[];
extern s32 D_00182BD8[];
extern s16 D_00183A56;
extern s16 D_00183A60;
extern u8 D_000D5060;
extern s8 func_00092270(s32 a, s32 b);

s32 func_0004E2F0(struct unk_0175 *obj)
{
    s32 result;
    s32 i;
    s32 off;
    s32 n;

    result = -1;
    i = 0;
    off = 0;
    for (; i < D_00183A56; off += 4, i++) {
        if ((s32)obj == *(s32 *)((char *)D_00182AD4 + off)) {
            result = 2;
            break;
        }
    }
    n = D_00183A60;
    i = 0;
    off = 0;
    for (; i < n; off += 4, i++) {
        if ((s32)obj == *(s32 *)((char *)D_00182BD8 + off)) {
            result = 7;
            break;
        }
    }
    if (result == -1 && obj->x_02 != -1) {
        if (obj->x_12c == 0) {
            result = 2;
        } else {
            if (func_00092270((s32)obj->x_12c, 0)
                || func_00092270(0, (s32)obj->x_12c)) {
                if (obj->x_174 == D_000D5060 && obj->x_10a == -1) {
                    result = 7;
                }
            }
        }
    }
    return result;
}
