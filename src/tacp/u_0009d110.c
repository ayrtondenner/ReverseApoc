/*
 * src/tacp/u_0009d110.c: translation unit u_0009d110 of TACP.EXE, 0x0009D110..0x0009D140 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0009d110`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

extern void func_0009CFF0(s32 eax_in, s32 edx_in, s32 ebx_in, void *ptr, void *p1, void *p2);
extern void func_00075E40(s32 a, s32 b, s32 c);

void func_0009D110(s32 a, s32 b, s32 c)
{
    s16 r[6];

    func_0009CFF0(a, b, c, &r[4], &r[2], &r[0]);
    func_00075E40((s32)r[4], (s32)r[2], (s32)r[0]);
}
