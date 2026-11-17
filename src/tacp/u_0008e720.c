/*
 * src/tacp/u_0008e720.c: translation unit u_0008e720 of TACP.EXE, 0x0008E720..0x00090990 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0008e720`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0008E770);
INCLUDE_ASM(func_0008F2F0);
INCLUDE_ASM(func_0008F3F0);
INCLUDE_ASM(func_0008F7F0);
INCLUDE_ASM(func_0008FB80);

struct unk_02BD {
    /* 0x000 */ u8 pad_000[0x224];
    /* 0x224 */ s16 field_224;
    /* 0x226 */ u8 pad_226[0x96];
    /* 0x2BC */ u8 flags;
}; /* size: at least 0x2BD */

struct unk_0004 {
    /* 0x00 */ int v;
}; /* size: 0x04 */

int func_00091000(struct unk_02BD *a, int b, int c, int d, int e);
int func_00090990(struct unk_02BD *a, int mode, int amount, int flag);

/* int or void: the bytes cannot tell (eax holds func_00090990's result at ret); the callers decide. */
void func_00090960(struct unk_02BD *a, int b, int c, int d, volatile int e, struct unk_0004 f)
{
    int ee;

    ee = e;
    func_00090990(a, a->field_224, func_00091000(a, b, d, ee, f.v), 1);
}

int func_00090940(struct unk_02BD *a, struct unk_02BD *b)
{
    int x;

    x = (u8)(a->flags ^ 4);
    return (x | (u8)(b->flags ^ 4)) ^ 4;
}
