/*
 * src/tacp/u_00017000.c: translation unit u_00017000 of TACP.EXE, 0x00017000..0x000189C0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00017000`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00017000);
INCLUDE_ASM(func_00017440);
INCLUDE_ASM(func_00017630);

extern char *D_000E6CEC;
extern int D_000E6D0C;

/* void: EAX only holds a leftover pointer at ret; the callers decide. */
void func_00017400(void)
{
    char *q;
    char *p;
    int v;

    q = D_000E6CEC - 6;
    p = q;
    while ((v = *(int *)q) != 0) {
        **(char **)p = p[4];
        q = p - 6;
        p = q;
    }
    D_000E6D0C = v;
    q = p + 6;
    D_000E6CEC = q;
}
