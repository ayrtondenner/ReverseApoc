/*
 * src/tacp/u_0003b110.c: translation unit u_0003b110 of TACP.EXE, 0x0003B110..0x0003B400 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0003b110`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0003B110);
INCLUDE_ASM(func_0003B1C0);
INCLUDE_ASM(func_0003B290);
extern char D_002B6EDC[];
extern char D_002B6F66[];
int func_0003B1C0(int);

void func_0003B3D0(int r_eax)
{
    int r_edx;

    r_edx = (int)D_002B6EDC;
    if (((unsigned)(int)D_002B6EDC) >= ((unsigned)(int)D_002B6F66)) goto L2F74C;
L2F72E:;
    if ((*(int *)((char *)r_edx + 12)) == 0) goto L2F741;
    if ((*(int *)((char *)r_edx + 8)) == 0) goto L2F741;
    func_0003B1C0(r_edx);
L2F741:;
    r_edx = r_edx + 46;
    if (((unsigned)r_edx) < ((unsigned)(int)D_002B6F66)) goto L2F72E;
L2F74C:;
    return;
}
