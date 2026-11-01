/*
 * src/ufo2p/u_0002f460.c: translation unit u_0002f460 of UFO2P.EXE, 0x0002F460..0x0002F750 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0002f460`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0002F460);
INCLUDE_ASM(func_0002F510);
INCLUDE_ASM(func_0002F5E0);

extern char D_00170CD0[];
extern char D_00170E9C[];
int func_0002F510(int);

void func_0002F720(int r_eax)
{
    int r_edx;

    r_edx = (int)D_00170CD0;
    if (((unsigned)(int)D_00170CD0) >= ((unsigned)(int)D_00170E9C)) goto L2F74C;
L2F72E:;
    if ((*(int *)((char *)r_edx + 12)) == 0) goto L2F741;
    if ((*(int *)((char *)r_edx + 8)) == 0) goto L2F741;
    func_0002F510(r_edx);
L2F741:;
    r_edx = r_edx + 46;
    if (((unsigned)r_edx) < ((unsigned)(int)D_00170E9C)) goto L2F72E;
L2F74C:;
    return;
}

