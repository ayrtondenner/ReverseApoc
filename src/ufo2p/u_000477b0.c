/*
 * src/ufo2p/u_000477b0.c: translation unit u_000477b0 of UFO2P.EXE, 0x000477B0..0x00048D30 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000477b0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000477B0);
INCLUDE_ASM(func_000477F0);
INCLUDE_ASM(func_00047B70);
INCLUDE_ASM(func_00047D70);
INCLUDE_ASM(func_00047FB0);
INCLUDE_ASM(func_000480B0);
INCLUDE_ASM(func_00048250);
#include "common.h"

struct tile_483a0 {
    s16 sprite;
    u8 pad[50];
};

extern s16 D_000D4D74;
extern s16 D_000D4D72;
extern u16 (*D_00182DFC)[100];
extern struct tile_483a0 D_0015309A[];
extern int *D_00182D68;
extern int D_000E7188;
extern char *D_00182DB4;
void func_00017C79(void);
void func_00016F2B(char *, int, int);

void func_000483A0(s16 rows)
{
    s16 j;
    s16 col;
    u16 x;
    u16 *p;
    s16 s;

    if (D_000D4D74 < 99) {
        D_000D4D74++;
        func_00017C79();
        p = &D_00182DFC[D_000D4D74 + 43][D_000D4D72];
        for (j = 0; j < rows; j++) {
            for (col = D_000D4D72, x = 0; col < D_000D4D72 + 80; col++, p++, x += 8) {
                if (col < 100 && D_000D4D74 + 43 < 100 && col >= 0 && D_000D4D74 + 43 >= 0) {
                    if (*p != 0) {
                        s = D_0015309A[*p].sprite;
                        if (s != 0) {
                            func_00016F2B(D_00182DB4 + D_00182D68[s], x, 344);
                        }
                    }
                } else if (j == 0) {
                    func_00016F2B(D_00182DB4 + D_00182D68[D_000E7188], x, 344);
                }
            }
            p += 9920;
        }
    }
}

INCLUDE_ASM(func_000484F0);
INCLUDE_ASM(func_00048640);
INCLUDE_ASM(func_000487A0);
INCLUDE_ASM(func_00048830);

int func_00046400(int, int, int, int, int);

void func_00048860(void)
{
    func_00046400(244, 180, 324, 100, 115);
    func_00046400(324, 100, 412, 188, 115);
    func_00046400(412, 188, 332, 268, 115);
    func_00046400(332, 268, 244, 180, 115);
    return;
}

INCLUDE_ASM(func_000488E0);
INCLUDE_ASM(func_00048A10);
