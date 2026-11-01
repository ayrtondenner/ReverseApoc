/*
 * src/ufo2p/u_0006ee50.c: translation unit u_0006ee50 of UFO2P.EXE, 0x0006EE50..0x0006FE10 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0006ee50`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0006EE50);
INCLUDE_ASM(func_0006EEF0);
INCLUDE_ASM(func_0006F3C0);
INCLUDE_ASM(func_0006F600);
INCLUDE_ASM(func_0006F750);
INCLUDE_ASM(func_0006F800);
INCLUDE_ASM(func_0006F830);
INCLUDE_ASM(func_0006F9B0);
INCLUDE_ASM(func_0006FC80);
INCLUDE_ASM(func_0006FD20);

extern int daily_history[27][56];
extern int daily_history_from_slot1[27][56];

/* Shifts each of 27 rows of 56 ints up by one slot (row stride 0xE0). EAX is unused: void. */
void daily_history_age(void)
{
    int i;
    int j;

    for (i = 0; i < 27; i++) {
        for (j = 55; j > 0; j--) {
            daily_history_from_slot1[i][j - 1] = daily_history[i][j - 1];
        }
    }
}
