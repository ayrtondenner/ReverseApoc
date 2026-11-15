/*
 * src/tacp/u_00090990.c: translation unit u_00090990 of TACP.EXE, 0x00090990..0x00091380 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00090990`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00090990);
INCLUDE_ASM(func_00090C50);
INCLUDE_ASM(func_00091000);

struct unk_0466 {
    /* 0x000 */ u8 pad_000[0x214];
    /* 0x214 */ s16 a;
    /* 0x216 */ s16 b;
    /* 0x218 */ s16 c;
    /* 0x21a */ u8 pad_21a[0x202];
    /* 0x41c */ s16 state;
    /* 0x41e */ u8 pad_41e[0x40];
    /* 0x45e */ s16 d;
    /* 0x460 */ s16 e;
    /* 0x462 */ s16 f;
    /* 0x464 */ s16 flag;
}; /* size: 0x466 */

extern void func_00091000(struct unk_0466 *, int, int, int, int);

/* The return value is unused in the target. */
void func_00090FA0(struct unk_0466 *p)
{
    int flag, x, y, z;
    if (p->state != -1) {
        flag = p->flag <= 1;
        x = p->d;
        y = p->e;
        z = p->f;
    } else {
        x = p->a;
        y = p->b;
        z = p->c;
        flag = 0;
    }
    func_00091000(p, flag, x, y, z);
}
