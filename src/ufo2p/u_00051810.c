/*
 * src/ufo2p/u_00051810.c: translation unit u_00051810 of UFO2P.EXE, 0x00051810..0x00051A90 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00051810`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00051810);
extern char D_00183A56[];
extern char D_000D4E28[];
extern char hover_info_changed[];
extern char D_00183A80[];

void func_00051A60(void)
{
    if ((*(short *)((D_00183A56))) <= 0) goto L51A8B;
    *(short *)((D_000D4E28)) = 9;
    *(short *)((hover_info_changed)) = 1;
    *(short *)((D_00183A80)) = 1;
L51A8B:;
    return;
}

