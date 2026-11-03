/*
 * src/tacp/u_00095780.c: translation unit u_00095780 of TACP.EXE, 0x00095780..0x000974D0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00095780`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00095780);
typedef struct {
    char pad0[4];
    char kind;
    char who;
    char pad6[8];
    short value;
    short index;
} Msg00095800;

extern short D_0010A306[][590];
extern int D_0027EFC0;
Msg00095800 *func_00021180(void);

void func_00095800(int who, int index, short value)
{
    Msg00095800 *m;

    if (value != D_0010A306[who][index]) {
        if (D_0027EFC0 == 0) {
            m = func_00021180();
            if (m != 0) {
                m->kind = 31;
                m->who = who;
                m->index = index;
                m->value = value;
            }
        } else {
            D_0010A306[who][index] = value;
        }
    }
}

INCLUDE_ASM(func_00095850);
INCLUDE_ASM(func_00095880);
INCLUDE_ASM(func_00095CA0);
INCLUDE_ASM(func_00096130);
INCLUDE_ASM(func_00096940);
INCLUDE_ASM(func_00096B40);
INCLUDE_ASM(func_00096BB0);
INCLUDE_ASM(func_00096C50);
INCLUDE_ASM(func_00096F50);
INCLUDE_ASM(func_00097370);
