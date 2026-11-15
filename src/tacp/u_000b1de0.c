/*
 * src/tacp/u_000b1de0.c: translation unit u_000b1de0 of TACP.EXE, 0x000B1DE0..0x000B2040 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_000b1de0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000B1FE0);

struct unk_049C {
    /* 0x000 */ s16 kind;
    /* 0x002 */ u8 pad_002[0x1E];
    /* 0x020 */ s16 unk_020;
    /* 0x022 */ u8 pad_022[0x04];
    /* 0x026 */ s16 unk_026;
    /* 0x028 */ u8 pad_028[0x07];
    /* 0x02F */ u8 unk_02F;
    /* 0x030 */ u8 pad_030[0x32];
    /* 0x062 */ s16 unk_062;
    /* 0x064 */ s16 unk_064;
    /* 0x066 */ u8 pad_066[0x0C];
    /* 0x072 */ u8 unk_072;
    /* 0x073 */ u8 unk_073;
    /* 0x074 */ u8 pad_074[0x428];
}; /* size: 0x49C */

extern struct unk_049C tacrec_table[];
int func_000B1FE0(s16 a);
u8 func_00021B30(s16 a, s16 b);
s16 func_000B1DE0(s16 a, s16 b);

/* void: EAX at ret holds only leftovers of the last branch */
void func_000B1E50(s16 a, s16 b, s16 c)
{
    struct unk_049C *p;
    struct unk_049C *q;
    int total, amount, n, i;

    p = &tacrec_table[a];
    if (b != 0) {
        q = tacrec_table;
        total = func_000B1FE0(p->unk_020) + (p->unk_02F + 4);
        for (i = 0; i < 60; i++, q++) {
            if (q->kind != -1 && q->unk_064 != 0 && q->unk_073 != 0) {
                if (p->unk_020 == q->unk_020) {
                    amount = (p->unk_02F + 4) * 100 / total;
                    amount = (15 - q->unk_073) * amount / 10;
                    amount = (12 - func_000B1DE0(q->unk_026, q->unk_020)) * amount / 10;
                    if (amount < q->unk_072)
                        q->unk_072 -= amount;
                    else
                        q->unk_072 = 0;
                } else if (func_00021B30(q->unk_020, p->unk_020)) {
                    n = p->unk_02F + 4;
                    amount = n * 15 / total;
                    if (amount > n)
                        amount = n;
                    q->unk_072 += amount;
                    if (q->unk_072 > 100)
                        q->unk_072 = 100;
                }
            }
        }
    } else {
        amount = c * 50 / p->unk_062;
        amount = (15 - p->unk_073) * amount / 10;
        if (amount < p->unk_072)
            p->unk_072 -= amount;
        else
            p->unk_072 = 0;
    }
}

s16 func_000B1DE0(s16 a, s16 b)
{
    struct unk_049C *p;
    s16 i;
    s16 best;

    p = tacrec_table;
    best = 0;
    for (i = 0; i < 60; i++, p++) {
        if (p->kind != -1 && p->unk_064 != 0 && p->unk_020 == b && p->unk_026 == a
            && (s16)p->unk_02F > best) {
            best = p->unk_02F;
        }
    }
    return best;
}
