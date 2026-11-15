/*
 * src/tacp/u_000778d0.c: translation unit u_000778d0 of TACP.EXE, 0x000778D0..0x00077D90 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_000778d0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000778D0);
INCLUDE_ASM(func_00077970);
INCLUDE_ASM(func_000779E0);
INCLUDE_ASM(func_00077B90);
INCLUDE_ASM(func_00077BB8);
INCLUDE_ASM(func_00077BE0);
INCLUDE_ASM(func_00077C08);
INCLUDE_ASM(func_00077C30);
INCLUDE_ASM(func_00077C58);
INCLUDE_ASM(func_00077C80);
INCLUDE_ASM(func_00077CD0);

char *func_00021180(void);
extern unsigned char D_00292F2C;

/* void: EAX at ret only holds the callee's result */
void func_000779C0(void)
{
    char *p;

    p = func_00021180();
    if (p != 0) {
        p[4] = 0x12;
        D_00292F2C = 1;
    }
}
