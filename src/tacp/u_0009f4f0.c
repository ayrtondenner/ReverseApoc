/*
 * src/tacp/u_0009f4f0.c: translation unit u_0009f4f0 of TACP.EXE, 0x0009F4F0..0x0009F5F0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0009f4f0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0009F4F0);

struct unk_0072 {
    /* 0x00 */ u8 flag;
    /* 0x01 */ u8 data[0x71];
}; /* size: 0x72 */

extern struct unk_0072 D_00276BD4[];

/* void: EAX holds i * 0x72 at ret, not a result; the callers decide. */
void func_0009F5E0(int i)
{
    D_00276BD4[i].flag = 0;
}
