/*
 * src/tacp/u_00087ff0.c: translation unit u_00087ff0 of TACP.EXE, 0x00087FF0..0x00089060 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00087ff0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00088040);
INCLUDE_ASM(func_00088210);
INCLUDE_ASM(func_00088390);
INCLUDE_ASM(func_000884A0);
INCLUDE_ASM(func_00088830);
INCLUDE_ASM(func_000888C0);
INCLUDE_ASM(func_00088F20);
INCLUDE_ASM(func_00089030);

/* func_00021180 returns a record pointer or NULL (callee listing not read). */
extern u8 *func_00021180(s32 a);

/* s16 guessed: EAX holds the +8 value or the NULL pointer at ret (callers not read). */
s16 func_00087FF0(s32 a, volatile s16 d, s16 b, s16 c)
{
    u8 *p;
    s16 t;

    p = func_00021180(a);
    if (p != 0) {
        p[4] = 0x15;
        *(s16 *)(p + 0x10) = (s16)a;
        p[5] = (u8)d;
        t = (c + 1) * -1;
        *(s16 *)(p + 0xE) = b;
        *(s16 *)(p + 0xA) = c;
        *(s16 *)(p + 8) = t;
        return t;
    }
    return (s16)(s32)p;
}

void func_000883F0(s32 a)
{
    u8 *p;

    p = func_00021180(a);
    if (p != 0) {
        p[4] = 0x28;
        p[5] = (u8)a;
    }
}

struct unk_0014 {
    /* 0x00 */ s16 kind;
    /* 0x02 */ s16 unk_02;
    /* 0x04 */ s32 unk_04;
    /* 0x08 */ u8 unk_08[0xC];
}; /* size: 0x14 */

/* Record table and its end: the target takes their addresses (mov edx, offset). */
extern struct unk_0014 D_001CA968[];
extern struct unk_0014 D_001CAE18[];

/* void: EAX is not read after the call (callee listing not read). */
extern void func_00088040(struct unk_0014 *p);

void func_00088410(s32 a)
{
    struct unk_0014 *p;

    p = D_001CA968;
    if (p < D_001CAE18) {
        do {
            if (p->kind != 0 && p->unk_04 == a) {
                func_00088040(p);
            }
            p++;
        } while (p < D_001CAE18);
    }
}

/* void: callers' use of EAX is not read; the target has no explicit result. */
void func_00088450(s32 a)
{
    struct unk_0014 *p;

    p = D_001CA968;
    if (p < D_001CAE18) {
        do {
            if (p->kind != 0 &&
                (p->unk_04 == a || *(s32 *)p->unk_08 == a)) {
                func_00088040(p);
            }
            p++;
        } while (p < D_001CAE18);
    }
}
