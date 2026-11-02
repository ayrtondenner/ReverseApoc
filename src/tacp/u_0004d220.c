/*
 * src/tacp/u_0004d220.c: translation unit u_0004d220 of TACP.EXE, 0x0004D220..0x0004E690 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0004d220`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"


int func_0004DAA0(int);
int func_000B4D10(int);
void func_0004F470(int);
int func_0001C410(int);

int func_0004D220(int r_eax)
{
    *(short *)((char *)r_eax + 540) = 0;
    *(short *)((char *)r_eax + 40) = (*(unsigned short *)((char *)r_eax)) << 4;
    func_0004DAA0(r_eax);
    func_000B4D10(r_eax);
    *(unsigned short *)((char *)r_eax + 206) = *(unsigned short *)((char *)r_eax + 208);
    func_0004F470(r_eax);
    r_eax = func_0001C410(r_eax);
    return r_eax;
}

INCLUDE_ASM(func_0004D270);
INCLUDE_ASM(func_0004D2D0);
INCLUDE_ASM(func_0004D360);
INCLUDE_ASM(func_0004D570);
INCLUDE_ASM(func_0004D870);
INCLUDE_ASM(func_0004DAA0);
INCLUDE_ASM(func_0004DD90);
INCLUDE_ASM(func_0004E1A0);
INCLUDE_ASM(func_0004E320);
