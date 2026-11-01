/*
 * src/ufo2p/u_000c1440.c: translation unit u_000c1440 of UFO2P.EXE, 0x000C1440..0x000C1454 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000c1440`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000C1445);

int unlink(const char *path);

int file_delete(const char *path)
{
    return unlink(path);
}
