/*
 * src/tacp/u_0003b450.c: translation unit u_0003b450 of TACP.EXE, 0x0003B450..0x0003B710 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_0003b450`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

struct unk_002E {
    /* 0x00 */ u8 pad_00[4];
    /* 0x04 */ s32 value;
    /* 0x08 */ u8 pad_08[4];
    /* 0x0C */ s32 flag;
    /* 0x10 */ u8 pad_10[8];
    /* 0x18 */ u32 limit;
    /* 0x1C */ u8 active;
    /* 0x1D */ u8 pad_1d[0x11];
};
extern struct unk_002E D_002B6EDC[];
extern struct unk_002E D_002B6F66[];
extern s32 D_002CCA94;
u32 func_00011500(void);
void func_0003B710(struct unk_002E *p);

void func_0003B450(void)
{
    u32 c;
    u32 t;
    struct unk_002E *p;

    c = func_00011500();
    p = D_002B6EDC;
    t = c;
    if (p >= D_002B6F66) {
        return;
    }
    do {
        if (p->flag != 0 && p->value == D_002CCA94) {
            t -= p->limit;
            if (t > 4 || p->active != 0) {
                return;
            }
            func_0003B710(p);
            return;
        }
        p++;
    } while (p < D_002B6F66);
}
INCLUDE_ASM(func_0003B4A0);
INCLUDE_ASM(func_0003B680);
