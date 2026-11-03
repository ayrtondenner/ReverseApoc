/*
 * src/ufo2p/u_0005f750.c: translation unit u_0005f750 of UFO2P.EXE, 0x0005F750..0x00060050 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0005f750`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_0005F750);
INCLUDE_ASM(func_0005F7E0);
INCLUDE_ASM(func_0005F830);
INCLUDE_ASM(func_0005F9B0);
INCLUDE_ASM(func_0005FB50);
#include "common.h"

struct pos_5fbd0 {
    s16 x;
    s16 y;
    s16 z;
    s16 ok;
};

struct unit_5fbd0 {
    u8 pad_000[2];
    s16 f_002;
    u8 pad_004[0x30 - 0x04];
    s16 x_030;
    s16 y_032;
    s16 z_034;
    u8 pad_036[0x40 - 0x36];
    s16 dx_040;
    s16 dy_042;
    s16 dz_044;
    u8 pad_046[0x56 - 0x46];
    s16 x_056;
    s16 y_058;
    s16 z_05a;
    s16 x_05c;
    s16 y_05e;
    s16 z_060;
    u8 pad_062[0xCE - 0x62];
    u8 f_0ce;
    u8 pad_0cf[0xEC - 0xCF];
    s16 x_0ec;
    s16 y_0ee;
    s16 z_0f0;
    u8 pad_0f2[0x100 - 0xF2];
    s16 f_100;
    u8 pad_102[0x107 - 0x102];
    u8 f_107;
    u8 pad_108[2];
    s16 f_10a;
    u8 pad_10c[0x12C - 0x10C];
    s16 f_12c;
    u8 pad_12e[0x276 - 0x12E];
};

extern struct unit_5fbd0 D_00160FD8[];
extern u8 D_000D5060;
extern int D_000D5054;
extern s16 hover_info_changed;
struct pos_5fbd0 func_0004CD70(s16, s16, s16, s16);
s16 func_00073000(struct unit_5fbd0 *, int);
void func_0006BD50(void);
s16 func_0005FD80(s16, int);

s16 func_0005FBD0(s16 idx)
{
    s16 result;
    struct pos_5fbd0 p;
    s16 moved;
    struct unit_5fbd0 *u;

    u = &D_00160FD8[idx];
    result = 0;
    moved = 0;
    if (u->f_002 == 1 && u->f_10a != -1 && u->f_100 != 0) {
        p = func_0004CD70(u->f_10a, u->x_030, u->y_032, u->z_034);
        if (p.ok != 0) {
            if (u->z_034 != -1 && D_000D5060 > 1) {
                u->f_10a = -1;
                u->f_107 = 0;
                p.x = u->x_030;
                p.y = u->y_032;
                p.z = u->z_034;
                moved = 1;
                if (u->f_12c == 0 && func_00073000(u, 0) != 0) {
                    func_0006BD50();
                    if (D_000D5054 >= 3 && D_000D5054 < 7) {
                        hover_info_changed = 1;
                    }
                }
            } else if (func_0005FD80(idx, 1) != 0) {
                moved = 1;
            }
            if (moved != 0) {
                u->x_056 = u->x_0ec = u->x_030 = p.x;
                u->y_058 = u->y_0ee = u->y_032 = p.y;
                u->z_05a = u->z_0f0 = u->z_034 = p.z;
                u->x_05c = u->x_056 + u->dx_040;
                u->y_05e = u->y_058 + u->dy_042;
                u->z_060 = u->z_05a + u->dz_044;
                u->f_0ce = 9;
                result = 1;
            }
        }
    }
    return result;
}

INCLUDE_ASM(func_0005FD80);
INCLUDE_ASM(func_0005FE40);
INCLUDE_ASM(func_0005FFA0);
INCLUDE_ASM(func_00060000);
