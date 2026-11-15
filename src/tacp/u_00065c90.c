#include "common.h"

extern char tacrec_table[];
extern char D_0011B360[];

void func_00065C90(s16 *self)
{
    s16 *p;

    p = (s16 *)tacrec_table;
    if (p < (s16 *)D_0011B360) {
        do {
            if (p != self && p[0] != -1 && p[0x32] > p[0x40] &&
                self != p &&
                p[0x73] > self[0x70] && p[0x70] < self[0x73] &&
                p[0x74] > self[0x71] && p[0x71] < self[0x74] &&
                p[0x75] > self[0x72] && p[0x72] < self[0x75]) {
                if ((s32)self[0x40] + 10U >= 0xffU) {
                    self[0x40] = 0xff;
                } else {
                    self[0x40] += 10;
                }
            }
            p += 0x24e;
        } while (p < (s16 *)D_0011B360);
    }
}
