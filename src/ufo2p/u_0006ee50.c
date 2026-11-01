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

#define DAILY_HISTORY_ROWS 27
#define DAILY_HISTORY_SLOTS 56
#define DAILY_HISTORY_LAST_SLOT 55

/* daily_history_from_slot1 is the same table as daily_history, seen from slot 1 (4 bytes on); objdiff pairs
 * the copy only with two externs. */
extern int daily_history[DAILY_HISTORY_ROWS][DAILY_HISTORY_SLOTS];
extern int daily_history_from_slot1[DAILY_HISTORY_ROWS][DAILY_HISTORY_SLOTS];

/* daily_history_age: age the daily history table by one day
 * Moves every slot of each of the 27 rows of 56 ints one slot on (slot k to k + 1), dropping
 * the last slot; slot 0 keeps its old value for the caller to overwrite. Row stride 0xE0.
 * EAX is unused: void.
 * Address: UFO2P.EXE 0x0006FDD0
 * Evidence: call: 0x0004AB30 calls it once the hour counter at 0x000D4D68 reaches 0x18 (a new day)
 * Evidence: call: 0x0004AAF0 calls it between 0x0007A5D0 and 0x00098180, as 0x0004AB30 does daily
 */
void daily_history_age(void)
{
    int row;
    int slot;

    for (row = 0; row < DAILY_HISTORY_ROWS; row++) {
        for (slot = DAILY_HISTORY_LAST_SLOT; slot > 0; slot--) {
            daily_history_from_slot1[row][slot - 1] = daily_history[row][slot - 1];
        }
    }
}
