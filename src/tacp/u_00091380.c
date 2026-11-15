/*
 * src/tacp/u_00091380.c: translation unit u_00091380 of TACP.EXE, 0x00091380..0x00093080 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00091380`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00091380);
INCLUDE_ASM(func_00091470);
INCLUDE_ASM(func_00091C90);
INCLUDE_ASM(func_00091ED0);
INCLUDE_ASM(func_00092730);
INCLUDE_ASM(func_00092D10);

extern char tacrec_table[];
void func_0008E420(char *);
void func_00095630(int);
void func_00095780(int, int, short, short);

void func_00091410(int index)
{
    char *rec;

    rec = tacrec_table + index * 0x49c;
    if (rec[0x46c] != 0) {
        func_0008E420(rec);
        if (*(short *)(rec + 0x41a) != -1) {
            if (*(short *)(rec + 0x432) != -1) {
                func_00095630(*(short *)(rec + 0x432));
                return;
            }
            func_00095780(index, 0, -1, -1);
        }
    }
}
