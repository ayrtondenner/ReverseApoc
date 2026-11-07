/*
 * src/tacp/u_000414d0.c: translation unit u_000414d0 of TACP.EXE, 0x000414D0..0x00041780 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_000414d0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000414D0);
INCLUDE_ASM(func_00041530);
INCLUDE_ASM(func_000415F0);
INCLUDE_ASM(func_00041660);
INCLUDE_ASM(func_000416C0);

struct unk_0016 {
    /* 0x00 */ u8 pad_00[4];
    /* 0x04 */ u8 kind;
    /* 0x05 */ u8 unit;
    /* 0x06 */ s16 pad_06;
    /* 0x08 */ s16 field_08;
    /* 0x0A */ s16 field_0A;
    /* 0x0C */ s16 field_0C;
    /* 0x0E */ s16 field_0E;
    /* 0x10 */ s16 field_10;
    /* 0x12 */ s16 field_12;
    /* 0x14 */ s16 field_14;
}; /* size: 0x16 */

extern struct unk_0016 *func_00021180(void);

extern short D_000E6D42;
extern short D_001B24AC[];

/* void: the bytes cannot tell, EAX just holds the loop bound at ret. */
void func_00041720(short a, int b, int c, int d)
{
    struct unk_0016 *p;
    int i;
    int j;
    u8 unit;

    if (c != -1) {
        for (i = 0, j = 0; i < D_000E6D42; i++) {
            p = func_00021180();
            if (p != 0) {
                unit = *(u8 *)((char *)D_001B24AC + j);
                p->kind = 0xc;
                p->unit = unit;
                p->field_08 = a;
                p->field_0C = c;
                p->field_0A = b;
                p->field_12 = d;
            }
            j += 2;
        }
    }
}
