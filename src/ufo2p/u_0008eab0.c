/*
 * src/ufo2p/u_0008eab0.c: translation unit u_0008eab0 of UFO2P.EXE, 0x0008EAB0..0x00092250 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0008eab0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0008EAB0);
INCLUDE_ASM(func_0008EB50);
INCLUDE_ASM(func_0008ECA0);
INCLUDE_ASM(func_0008F370);
INCLUDE_ASM(func_0008F800);
INCLUDE_ASM(func_0008FC30);
INCLUDE_ASM(func_000911C0);
INCLUDE_ASM(func_000911E0);
INCLUDE_ASM(func_00091450);
INCLUDE_ASM(func_000915E0);
INCLUDE_ASM(func_00091730);
INCLUDE_ASM(func_00091A00);
INCLUDE_ASM(func_00091A90);
INCLUDE_ASM(func_00091AF0);

struct unk_0024 {
    /* 0x00 */ u8 pad_00[0x20];
    /* 0x20 */ s32 field_20;
}; /* size: 0x24 */

struct unk_002E {
    /* 0x00 */ struct unk_0024 *field_00;
    /* 0x04 */ struct unk_0024 *field_04;
    /* 0x08 */ s32 field_08;
    /* 0x0C */ s32 field_0C;
    /* 0x10 */ u8 pad_10[0x0D];
    /* 0x1D */ u8 field_1D;
    /* 0x1E */ u8 pad_1E[0x10];
}; /* size: 0x2E */

extern struct unk_002E D_00170CD0[];
extern struct unk_002E D_00170E9C[];

/* void: EAX is only a scratch register here, the bytes cannot tell void from int. */
void func_0008EB00(void)
{
    struct unk_002E *p;

    p = D_00170CD0;
    if (p < D_00170E9C) {
        do {
            if (p->field_0C != 0 && p->field_1D == 0) {
                p->field_00->field_20 = 0;
                p->field_04->field_20 = 0;
                p->field_0C = 0;
            }
            p++;
        } while (p < D_00170E9C);
    }
}
