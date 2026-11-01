/*
 * src/tacp/u_00023c00.c: translation unit u_00023c00 of TACP.EXE, 0x00023C00..0x00023C40 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00023c00`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

extern int type_hide_enabled;
extern unsigned char D_0027A809[];

int type_name_is_shown(int a, unsigned int b)
{
    int r = 1;

    if (a < 0 || a >= 0x57) {
        return 0;
    }
    if (type_hide_enabled != 0) {
        switch (b) {
        case 0:
            if (D_0027A809[a] != 0) {
                r = 0;
            }
            break;
        case 1:
            break;
        default:
            r = 1;
            break;
        }
    }
    return r;
}
