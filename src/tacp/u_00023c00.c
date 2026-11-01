/*
 * src/tacp/u_00023c00.c: translation unit u_00023c00 of TACP.EXE, 0x00023C00..0x00023C40 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00023c00`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

/* Number of entries in the per-type hidden-flag table: valid indices are 0..0x56. */
#define TYPE_INDEX_COUNT 0x57

extern int type_hide_enabled;
extern unsigned char type_hidden_flags[];

/* type_name_is_shown: tell whether a type's own name may be shown
 * Returns 0 for an index outside 0..0x56. Otherwise returns 1, except in mode 0 while the
 * gate flag type_hide_enabled is set and the type's byte in type_hidden_flags is nonzero: then 0.
 * Mode 1 and every other mode return 1.
 * Address: TACP.EXE 0x00023C00
 * Evidence: call: the caller at 0x000521D5 passes a type byte from the 0x30-stride table at 0x000EA2C0 with mode 0
 * Evidence: call: on 0 that caller shows text 0x23/0x33 via 0x0005B360, on 1 the type's own text (2, type)
 */
int type_name_is_shown(int type_index, unsigned int mode)
{
    int is_shown = 1;

    if (type_index < 0 || type_index >= TYPE_INDEX_COUNT) {
        return 0;
    }
    if (type_hide_enabled != 0) {
        switch (mode) {
        case 0:
            if (type_hidden_flags[type_index] != 0) {
                is_shown = 0;
            }
            break;
        case 1:
            break;
        default:
            is_shown = 1;
            break;
        }
    }
    return is_shown;
}
