/*
 * src/tacp/u_00063100.c: translation unit u_00063100 of TACP.EXE, 0x00063100..0x000642E0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00063100`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00063100);
INCLUDE_ASM(func_000631E0);
INCLUDE_ASM(func_000635E0);
INCLUDE_ASM(func_00063C90);
INCLUDE_ASM(func_00063FB0);
INCLUDE_ASM(func_00064050);

extern char tacrec_table[];
extern int D_000E6C24;

/* void: EAX holds only the record pointer at ret, which no caller reads. */
void func_00063560(short idx)
{
    char *rec;

    rec = tacrec_table + idx * 0x49C;
    if (*(short *)(rec + 0x250) != 0) {
        if (D_000E6C24 >= *(short *)(rec + 0x250)) {
            *(short *)(rec + 0x250) = 0;
        } else {
            *(short *)(rec + 0x250) -= D_000E6C24;
        }
    }
    if (*(short *)(rec + 0x252) != 0) {
        if (*(short *)(rec + 0x252) <= D_000E6C24) {
            *(short *)(rec + 0x252) = 0;
        } else {
            *(short *)(rec + 0x252) -= D_000E6C24;
        }
    }
}
