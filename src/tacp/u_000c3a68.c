/*
 * src/tacp/u_000c3a68.c: translation unit u_000c3a68 of TACP.EXE, 0x000C3A68..0x000C3A98 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_000c3a68`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

int __clock(const char *path);

int func_000C3A68(const char *file_path)
{
    return __clock(file_path);
}
#define CASE_LOWER_FIRST 0x61
#define CASE_LOWER_LAST 0x7a
#define CASE_SHIFT 0x20

int func_000C3A6D(int ch)
{
    if (ch >= CASE_LOWER_FIRST && ch <= CASE_LOWER_LAST) {
        ch -= CASE_SHIFT;
    }
    return ch;
}
INCLUDE_ASM(func_000C3A7B);
INCLUDE_ASM(func_000C3A89);
