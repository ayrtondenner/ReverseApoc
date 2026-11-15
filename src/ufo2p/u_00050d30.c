/*
 * src/ufo2p/u_00050d30.c: translation unit u_00050d30 of UFO2P.EXE, 0x00050D30..0x00051150 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00050d30`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00050D30);
INCLUDE_ASM(func_00050D70);
INCLUDE_ASM(func_00050EA0);
INCLUDE_ASM(func_00050EB0);
INCLUDE_ASM(func_00050EC0);
INCLUDE_ASM(func_00050EE0);
INCLUDE_ASM(func_00050FB0);
INCLUDE_ASM(func_000510D0);
INCLUDE_ASM(func_00051110);

extern int D_000D5054;
extern int D_00182A20[];
extern short hover_info_changed;

int func_00050FB0(int a);

/* void: EAX at ret holds only the callee's result or the reloaded index. */
void func_00050F50(void)
{
    int one;
    int i;

    if (D_00182A20[D_000D5054] + 14 <= func_00050FB0(D_000D5054)) {
        one = 1;
        i = D_000D5054;
        hover_info_changed = one;
        D_00182A20[i]++;
    }
}
