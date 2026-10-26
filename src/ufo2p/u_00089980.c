/*
 * src/ufo2p/u_00089980.c: translation unit u_00089980 of UFO2P.EXE, 0x00089980..0x0008B750 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00089980`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00089980);
INCLUDE_ASM(func_0008A0C0);
INCLUDE_ASM(func_0008A120);
INCLUDE_ASM(func_0008A140);
INCLUDE_ASM(func_0008A160);
INCLUDE_ASM(func_0008A180);
INCLUDE_ASM(func_0008A1A0);
INCLUDE_ASM(func_0008A1C0);
INCLUDE_ASM(func_0008A1E0);
INCLUDE_ASM(func_0008A420);
INCLUDE_ASM(func_0008A900);
INCLUDE_ASM(func_0008AAF0);
INCLUDE_ASM(func_0008B4A0);
INCLUDE_ASM(func_0008B530);

/* void: EAX only holds the callee's result at ret; the callers decide. */
void func_00089980(int a, int b);

/* void: EAX only holds func_00089980's result at ret; the callers decide. */
void func_0008A100(void)
{
    extern short D_001A714C;

    func_00089980(4, -1);
    D_001A714C = 0;
}

extern short D_001A714C;

/* void: EAX only holds func_00089980's result at ret; the callers decide. */
void func_0008A0E0(void)
{
    func_00089980(3, -1);
    D_001A714C = 0;
}
