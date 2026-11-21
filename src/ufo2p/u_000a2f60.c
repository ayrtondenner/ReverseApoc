/*
 * src/ufo2p/u_000a2f60.c: translation unit u_000a2f60 of UFO2P.EXE, 0x000A2F60..0x000A31E0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000a2f60`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000A2F60);
INCLUDE_ASM(func_000A2F88);
INCLUDE_ASM(func_000A2FB0);
INCLUDE_ASM(func_000A2FD8);
INCLUDE_ASM(func_000A3000);
INCLUDE_ASM(func_000A3050);

extern int D_00182CB0;
extern char D_000D3160[];
extern int *D_00182D78;
extern int D_00182D5C;

void func_0002E430(void);
void func_0002E470(int a);
void func_000A3970(void);
signed char func_000B7800(char *s);
void func_0002E640(int a, int b, int c, int d, int e, int f, int g, void (*h)(void), int i);

/* void: EAX at ret holds only func_0002E640's result; the callers decide. */
void func_000A3180(void)
{
    int index;
    int base;

    func_0002E430();
    func_0002E470(D_00182CB0);
    func_0002E640(0x25a, 0x1bb, 0x27c, 0x1dd, 0,
                  (index = D_00182D78[5], base = D_00182D5C, index * 4 + base),
                  func_000B7800(D_000D3160), func_000A3970, 0);
}
