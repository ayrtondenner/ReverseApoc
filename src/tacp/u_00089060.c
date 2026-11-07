/*
 * src/tacp/u_00089060.c: translation unit u_00089060 of TACP.EXE, 0x00089060..0x000890A0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00089060`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

/* Only the field at 0x20 is known; the full size is not. */
struct unk_0022 {
    /* 0x00 */ u8 pad_00[0x20];
    /* 0x20 */ s16 unk_20;
}; /* size: 0x22 */

struct unk_0014 {
    /* 0x00 */ s16 kind;
    /* 0x02 */ s16 unk_02;
    /* 0x04 */ s32 unk_04;
    /* 0x08 */ struct unk_0022 *unk_08;
    /* 0x0C */ s16 unk_0C;
    /* 0x0E */ s16 unk_0E;
    /* 0x10 */ s32 unk_10;
}; /* size: 0x14 */

extern struct unk_0014 D_001CA968[];
extern struct unk_0014 D_001CAE18[];

s16 func_00089060(struct unk_0022 *a)
{
    struct unk_0014 *p;
    s16 result;

    p = D_001CA968;
    result = a->unk_20;
    if (p < D_001CAE18) {
        do {
            if (p->kind == 6 && p->unk_02 > 0 && p->unk_08 == a) {
                result = p->unk_0E;
                goto done;
            }
            p++;
        } while (p < D_001CAE18);
    }
done:
    return result;
}
