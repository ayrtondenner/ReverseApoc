/*
 * src/tacp/u_00040e30.c: translation unit u_00040e30 of TACP.EXE, 0x00040E30..0x00041140 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00040e30`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00040E30);
INCLUDE_ASM(func_000410C0);

struct unk_049C {
    /* 0x000 */ u8 pad_000[0xAA];
    /* 0x0AA */ s16 x;
    /* 0x0AC */ s16 y;
    /* 0x0AE */ u8 pad_0AE[0x3EE];
}; /* size: 0x49C */

extern struct unk_049C tacrec_table[];
extern int D_001ED374;
extern int D_001ED378;

short func_0004F190(int a, int b, int c, int d);

int func_00041070(short index)
{
    int v;
    int x;
    int y;
    int w;
    int d;

    v = index * 0x49C;
    d = D_001ED378;
    w = D_001ED374;
    v += (int)tacrec_table;
    d = (short)d;
    x = ((struct unk_049C *)v)->x;
    y = ((struct unk_049C *)v)->y;
    v = (short)w;
    y = (short)y;
    w = (short)x;
    return func_0004F190(w, y, v, d);
}
