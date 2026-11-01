/*
 * src/ufo2p/u_00060140.c: translation unit u_00060140 of UFO2P.EXE, 0x00060140..0x000602E0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00060140`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00060140);

struct unk_0120 {
    /* 0x000 */ u8 pad_000[0x4];
    /* 0x004 */ s16 kind;
    /* 0x006 */ u8 pad_006[0x114];
    /* 0x11A */ s16 slots[3];
}; /* size: 0x120 (not read past 0x120) */

short func_000602A0(struct unk_0120 *p)
{
    short n;
    short i;

    n = 0;
    i = 0;
    do {
        n += p->slots[i] != -1;
        i++;
    } while (i < 3);
    if (p->kind == 0x21) {
        n = 1;
    }
    return n;
}
