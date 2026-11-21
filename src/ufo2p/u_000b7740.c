/*
 * src/ufo2p/u_000b7740.c: translation unit u_000b7740 of UFO2P.EXE, 0x000B7740..0x000B7A90 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000b7740`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000B7740);
INCLUDE_ASM(func_000B77E0);
INCLUDE_ASM(func_000B7800);
INCLUDE_ASM(func_000B78A0);
void func_000B78D0(void)
{
    return;
}
INCLUDE_ASM(func_000B78E0);

extern char *D_00138F80[];

char *_inline_strcpy(char *dst, const char *src);

/* void: EAX at ret holds the last byte copied, not a result. */
void func_000B7870(int index, char *dst)
{
    _inline_strcpy(dst, D_00138F80[index]);
}
