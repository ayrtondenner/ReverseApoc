/*
 * src/tacp/u_00056d70.c: translation unit u_00056d70 of TACP.EXE, 0x00056D70..0x00057870 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00056d70`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000570A0);
INCLUDE_ASM(func_000572C0);
INCLUDE_ASM(func_00057300);
INCLUDE_ASM(func_00057620);
INCLUDE_ASM(func_000576B0);
INCLUDE_ASM(func_00057780);

extern char *D_000E6C00;
extern int *D_000E6C04;
extern int D_000E6C14;
extern short D_000E6C18;
extern char *D_000E6CEC;
extern char *D_000E6CF0;
extern short D_000E6CF8;
extern int *D_000E6D00;
extern int *D_000E6D04;
void func_000443F0(void);
void func_00017400(void);

/*
 * Resets two pools: a byte pool based at D_000E6C00 (cursor D_000E6CEC, start D_000E6CF0)
 * and an int pool based at D_000E6C04 (cursor D_000E6D00, start D_000E6D04). The second
 * zero is written as D_000E6C14 ^ D_000E6C14 so that wcc386 emits a fresh `xor edx, edx`
 * before the D_000E6CF0 store, as the original does; a literal 0 or q ^ q is folded into the
 * first zero and sinks past that store.
 */
void func_00056D70(void)
{
    char *p;
    int *q;
    int *r;
    char *s;
    short w;

    p = D_000E6C00;
    *(int *)p = 0;
    q = D_000E6C04;
    p[4] = 0;
    D_000E6D00 = q;
    *q = 0;
    r = q + 2;
    D_000E6CEC = p;
    s = p + 6;
    r[-1] = 0;
    D_000E6D00 = r;
    D_000E6D04 = r;
    q = (int *)((int)r ^ (int)r);
    D_000E6CEC = s;
    D_000E6C14 = (int)q;
    w = (short)(D_000E6C14 ^ D_000E6C14);
    D_000E6CF0 = s;
    D_000E6C18 = w;
    func_000443F0();
    func_00017400();
    D_000E6CF8 = w;
}
