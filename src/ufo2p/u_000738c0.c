/*
 * src/ufo2p/u_000738c0.c: translation unit u_000738c0 of UFO2P.EXE, 0x000738C0..0x00075630 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000738c0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000738C0);

extern char D_000F3DC6[];

void func_000738E0(short r_eax)
{
    *(short *)((D_000F3DC6)) = r_eax;
    return;
}

INCLUDE_ASM(func_000738F0);
INCLUDE_ASM(func_00073E60);
INCLUDE_ASM(func_00073EE0);
INCLUDE_ASM(func_000740F0);
INCLUDE_ASM(func_000741E0);
INCLUDE_ASM(func_00075310);

struct unk_0006 {
    /* 0x00 */ s16 a;
    /* 0x02 */ s16 b;
    /* 0x04 */ s16 key;
}; /* size: 0x6 */

extern struct unk_0006 D_001A474C[];
extern s16 D_00183B00;
extern s16 D_00183B02;
extern u8 D_000D4CF8;
extern s16 D_000D4CFA;
extern s16 D_000D4CFC;

struct unk_0006 *func_000755E0(int key)
{
    struct unk_0006 *rec;
    int i;
    s16 w;
    s16 ra;
    s16 k;

    rec = D_001A474C;
    i = 0;
    do {
        if (rec->key == key) {
            break;
        }
        i++;
        rec++;
    } while (i < 0x1a);
    k = key;
    w = D_00183B02;
    ra = rec->a;
    D_000D4CF8 = k;
    w -= ra;
    k = rec->b;
    D_000D4CFA = w;
    w = D_00183B00 - k;
    D_000D4CFC = w;
    return rec;
}
