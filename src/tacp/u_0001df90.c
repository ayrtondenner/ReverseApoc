/*
 * src/tacp/u_0001df90.c: translation unit u_0001df90 of TACP.EXE, 0x0001DF90..0x0001EB30 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0001df90`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0001DF90);
INCLUDE_ASM(func_0001E000);
INCLUDE_ASM(func_0001E5D0);
INCLUDE_ASM(func_0001E660);
typedef struct {
    short type;
    char pad2[184];
    short x;
    short y;
    short z;
} Obj0001E860;

extern short D_000E4D6E;
extern int D_000E6BF8;
extern int D_000E6BFC;

void func_0001E860(Obj0001E860 *p, int *sx, int *sy)
{
    int x;
    int y;
    int z;

    x = p->x - p->y;
    y = (p->x + p->y) / 2;
    z = p->z;
    switch (p->type) {
    case 5:
        x -= 36;
        y -= 48;
        break;
    case 10:
        x -= 48;
        y -= 104;
        break;
    case 11:
        x -= 48;
        y -= 84;
        break;
    case 12:
        x -= 84;
        y -= 72;
        break;
    }
    y += D_000E4D6E * 40;
    *sx = x - D_000E6BF8;
    *sy = y - D_000E6BFC - z;
}

typedef struct {
    /* 0x00 */ unsigned short type;
    /* 0x02 */ char pad2[184];
    /* 0xBA */ short x;
    /* 0xBC */ short y;
    /* 0xBE */ short z;
} Obj0001E7B0; /* size: 0xC0 at least */

void func_0001E7B0(Obj0001E7B0 *p, int *sx, int *sy)
{
    int x;
    int y;
    int z;

    x = p->x - p->y;
    y = (p->x + p->y) / 2;
    z = p->z;
    switch (p->type) {
    case 5:
        x -= 36;
        y -= 78;
        break;
    case 10:
    case 11:
        x -= 48;
        y -= 104;
        break;
    case 12:
        x -= 84;
        y -= 122;
        break;
    }
    y += D_000E4D6E * 40;
    *sx = x;
    *sy = y - z;
}

INCLUDE_ASM(func_0001E900);
