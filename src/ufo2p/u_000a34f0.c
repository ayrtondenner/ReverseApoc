/*
 * src/ufo2p/u_000a34f0.c: translation unit u_000a34f0 of UFO2P.EXE, 0x000A34F0..0x000A3990 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000a34f0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000A34F0);
INCLUDE_ASM(func_000A3970);

void func_000A3990(void);

extern signed char D_0012EFAC;

/*
 * func_000A3980: calls func_000A3990, then returns the signed byte at D_0012EFAC widened
 * to int. Neither name is known yet.
 */
int func_000A3980(void)
{
    func_000A3990();
    return D_0012EFAC;
}
