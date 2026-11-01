/*
 * src/ufo2p/u_000c1544.c: translation unit u_000c1544 of UFO2P.EXE, 0x000C1544..0x000C156B (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000c1544`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 *
 * Four small runtime wrappers: a delay, ASCII upper and lower case conversion, and the clock.
 */
#include "common.h"

/* ASCII ranges and the distance between the two letter cases. */
#define CASE_LOWER_FIRST 0x61
#define CASE_LOWER_LAST 0x7a
#define CASE_UPPER_FIRST 0x41
#define CASE_UPPER_LAST 0x5a
#define CASE_SHIFT 0x20

/* Watcom runtime delay(); links as __delay_. */
void __delay(unsigned ms);

/* sys_delay: wait the given number of milliseconds
 * A 5-byte thunk: jmp __delay_. void: EAX at the jmp holds the argument only; the
 * callers decide. The argument's signedness is not visible in the bytes.
 * Address: UFO2P.EXE 0x000C1544
 * Evidence: call: the only instruction is a jmp to the Watcom runtime __delay_ (delay in ms)
 * Evidence: call: called from 0x00028E20, 0x00028F80, 0x000298E0, 0x00029900, 0x00029910, 0x0002D110
 */
void sys_delay(unsigned ms)
{
    __delay(ms);
}

/* char_to_upper: convert an ASCII letter to upper case
 * toupper-like: 'a'..'z' become 'A'..'Z', anything else is returned as is.
 * Address: UFO2P.EXE 0x000C1549
 * Evidence: call: the body subtracts 0x20 from values in 0x61..0x7A and returns the rest unchanged
 */
int char_to_upper(int ch)
{
    if (ch >= CASE_LOWER_FIRST && ch <= CASE_LOWER_LAST) {
        ch -= CASE_SHIFT;
    }
    return ch;
}

/* char_to_lower: convert an ASCII letter to lower case
 * tolower-like: 'A'..'Z' become 'a'..'z', anything else is returned as is.
 * Address: UFO2P.EXE 0x000C1557
 * Evidence: call: the body adds 0x20 to values in 0x41..0x5A and returns the rest unchanged
 */
int char_to_lower(int ch)
{
    if (ch >= CASE_UPPER_FIRST && ch <= CASE_UPPER_LAST) {
        ch += CASE_SHIFT;
    }
    return ch;
}

/* Watcom runtime clock(); links as __clock_. */
unsigned long __clock(void);

/* sys_clock: read the runtime clock tick count
 * unsigned long: EAX at the jmp holds __clock's result; the callers decide.
 * Address: UFO2P.EXE 0x000C1566
 * Evidence: call: the only instruction is a jmp to the Watcom runtime __clock_
 */
unsigned long sys_clock(void)
{
    return __clock();
}
