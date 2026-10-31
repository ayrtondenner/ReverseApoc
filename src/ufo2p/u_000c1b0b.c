/*
 * src/ufo2p/u_000c1b0b.c: translation unit u_000c1b0b of UFO2P.EXE, 0x000C1B0B..0x000C1B2A (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000c1b0b`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

int fseek(void *fp, long offset, int whence);
long ftell(void *fp);

/* fgetpos-like: store ftell(fp) in *pos, nonzero on failure (-1) */
int func_000C1B0B(void *fp, long *pos)
{
    return (*pos = ftell(fp)) == -1;
}

/* fsetpos-like: seek to *pos from the start (SEEK_SET) */
int func_000C1B1E(void *fp, long *pos)
{
    return fseek(fp, *pos, 0);
}
