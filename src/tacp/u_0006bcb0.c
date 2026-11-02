/*
 * src/tacp/u_0006bcb0.c: translation unit u_0006bcb0 of TACP.EXE, 0x0006BCB0..0x0006C750 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0006bcb0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0006BCB0);

typedef struct {
    short type;
    char pad[148];
    char b96;
} S0006BEE0;

int func_0006BEE0(S0006BEE0 *p)
{
    if ((p->type == 0 || (p->type >= 14 && p->type <= 20)
         || (p->type >= 22 && p->type <= 24) || p->type == 27)
        && p->b96 != 2) {
        return 1;
    }
    return 0;
}

INCLUDE_ASM(func_0006BF30);
INCLUDE_ASM(func_0006C090);
INCLUDE_ASM(func_0006C2C0);
