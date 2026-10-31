/*
 * src/ufo2p/u_000c1544.c: translation unit u_000c1544 of UFO2P.EXE, 0x000C1544..0x000C156B (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000c1544`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

/* Watcom runtime delay(); links as __delay_. */
void __delay(unsigned ms);

/* void: EAX at the jmp holds the argument only; the callers decide. */
void func_000C1544(unsigned ms)
{
    __delay(ms);
}

/* toupper-like: 'a'..'z' become 'A'..'Z', anything else is returned as is. */
int func_000C1549(int c)
{
    if (c >= 0x61 && c <= 0x7a) {
        c -= 0x20;
    }
    return c;
}

/* tolower-like: 'A'..'Z' become 'a'..'z', anything else is returned as is. */
int func_000C1557(int c)
{
    if (c >= 0x41 && c <= 0x5a) {
        c += 0x20;
    }
    return c;
}

/* Watcom runtime clock();links as __clock_. */
unsigned long __clock(void);

/* unsigned long: EAX at the jmp holds __clock's result; the callers decide. */
unsigned long func_000C1566(void)
{
    return __clock();
}
