/*
 * src/ufo2p/u_0005e910.c: translation unit u_0005e910 of UFO2P.EXE, 0x0005E910..0x0005F750 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0005e910`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0005E910);
INCLUDE_ASM(func_0005E970);
INCLUDE_ASM(func_0005EA00);
INCLUDE_ASM(func_0005EB20);
void func_0005EDA0(void)
{
    return;
}
INCLUDE_ASM(func_0005EDF0);
INCLUDE_ASM(func_0005EE60);
INCLUDE_ASM(func_0005EEA0);
INCLUDE_ASM(func_0005F110);
INCLUDE_ASM(func_0005F180);
INCLUDE_ASM(func_0005F230);
INCLUDE_ASM(func_0005F290);
INCLUDE_ASM(func_0005F320);
struct unk_0008 {
    /* 0x00 */ s16 f_00;
    /* 0x02 */ u8 data[0x06];
};
extern struct unk_0008 D_00143F88[];

struct unk_0008 *func_0005F3B0(void)
{
    struct unk_0008 *p;
    s16 i;

    p = D_00143F88;
    i = 0;
    do {
        if (p->f_00 == 0) {
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
struct unk_02BE {
    /* 0x000 */ s16 id;
    /* 0x002 */ u8 pad_002[0x13];
    /* 0x015 */ u8 active;
    /* 0x016 */ u8 data[0x2A8];
}; /* size: 0x2BE */
extern struct unk_02BE D_000D942E[];

s16 func_0005EDB0(s16 id)
{
    s16 r;
    s16 i;
    struct unk_02BE *p;

    r = -1;
    p = D_000D942E;
    i = 0;
    do {
        if (p->active != 0 && id == p->id) {
            r = i;
            break;
        }
        i++;
        p++;
    } while (i < 16);
    return r;
}
INCLUDE_ASM(func_0005F3E0);
INCLUDE_ASM(func_0005F410);
INCLUDE_ASM(func_0005F460);
INCLUDE_ASM(func_0005F5E0);
