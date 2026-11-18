/*
 * src/ufo2p/u_00053770.c: translation unit u_00053770 of UFO2P.EXE, 0x00053770..0x00059E20 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00053770`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00053770);
INCLUDE_ASM(func_000537C0);
INCLUDE_ASM(func_00053810);
INCLUDE_ASM(func_00053860);
INCLUDE_ASM(func_000538B0);
INCLUDE_ASM(func_000543D0);
struct unk_015E {
    /* 0x000 */ s16 id;
    /* 0x002 */ u8 data[0x15C];
};
extern struct unk_015E rec15e_table[];

struct unk_015E *func_000546A0(void)
{
    struct unk_015E *p;
    s16 i;

    p = rec15e_table;
    i = 0;
    do {
        if (p->id == -1) {
            break;
        }
        i++;
        p++;
    } while (i < 50);
    if (i == 50) {
        p = 0;
    }
    return p;
}
INCLUDE_ASM(func_000546D0);
INCLUDE_ASM(func_00054720);
INCLUDE_ASM(func_00054990);
INCLUDE_ASM(func_000564E0);
INCLUDE_ASM(func_000566B0);
INCLUDE_ASM(func_000571A0);
INCLUDE_ASM(func_000573A0);
INCLUDE_ASM(func_00057790);
INCLUDE_ASM(func_00057870);
INCLUDE_ASM(func_00057950);
INCLUDE_ASM(func_00057A80);
INCLUDE_ASM(func_00058040);
INCLUDE_ASM(func_00058190);
INCLUDE_ASM(func_000581D0);
INCLUDE_ASM(func_000582C0);
INCLUDE_ASM(func_00058390);
INCLUDE_ASM(func_00058400);
INCLUDE_ASM(func_000586C0);
INCLUDE_ASM(func_00058930);
INCLUDE_ASM(func_00058EB0);
INCLUDE_ASM(func_00059530);
INCLUDE_ASM(func_000596A0);
INCLUDE_ASM(func_00059AA0);
INCLUDE_ASM(func_00059B70);
