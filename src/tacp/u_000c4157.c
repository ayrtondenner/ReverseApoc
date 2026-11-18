/*
 * src/tacp/u_000c4157.c: translation unit u_000c4157 of TACP.EXE, 0x000C4157..0x000C4176 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_000c4157`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

long ftell(void *fp);

int func_000C4157(void *stream, long *position)
{
    return (*position = ftell(stream)) == -1;
}
int fseek(void *fp, long offset, int whence);

int func_000C416A(void *stream, long *position)
{
    return fseek(stream, *position, 0);
}
