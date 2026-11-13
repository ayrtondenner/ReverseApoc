/*
 * src/tacp/u_00079e00.c: translation unit u_00079e00 of TACP.EXE, 0x00079E00..0x0007A620 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00079e00`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00079E00);
INCLUDE_ASM(func_00079FE0);
INCLUDE_ASM(func_0007A000);

unsigned char func_0007A010(unsigned char r_eax)
{
    if ((r_eax >> 6) != 2) goto L7A021;
    return r_eax & 63;
L7A021:;
    return 0;
}

INCLUDE_ASM(func_0007A030);

unsigned char func_0007A040(unsigned char r_eax)
{
    if ((r_eax >> 6) != 1) goto L7A051;
    return r_eax & 63;
L7A051:;
    return 0;
}

INCLUDE_ASM(func_0007A060);

unsigned char func_0007A070(unsigned char r_eax)
{
    if ((r_eax >> 6) != 3) goto L7A081;
    return r_eax & 63;
L7A081:;
    return 0;
}

INCLUDE_ASM(func_0007A090);
INCLUDE_ASM(func_0007A0A0);
extern unsigned char D_00293050[];

unsigned char func_0007A0D0(unsigned char i)
{
    return D_00293050[i];
}

INCLUDE_ASM(func_0007A0E0);
INCLUDE_ASM(func_0007A140);
INCLUDE_ASM(func_0007A3A0);
INCLUDE_ASM(func_0007A500);
INCLUDE_ASM(func_0007A590);
