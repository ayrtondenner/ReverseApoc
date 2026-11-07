/*
 * src/ufo2p/u_00041ef0.c: translation unit u_00041ef0 of UFO2P.EXE, 0x00041EF0..0x000477B0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00041ef0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

extern char D_000D4CD8[];
extern char D_000D4CD6[];
extern char D_000D4CDC[];
extern char D_000D4CDA[];
int func_00046F30(void);

int func_00041EF0(void)
{
    int r_eax;

    *(short *)((D_000D4CD8)) = 0;
    *(short *)((D_000D4CD6)) = 0;
    *(short *)((D_000D4CDC)) = 352;
    *(short *)((D_000D4CDA)) = 640;
    r_eax = func_00046F30();
    return r_eax;
}

INCLUDE_ASM(func_00041F30);
INCLUDE_ASM(func_00042120);
INCLUDE_ASM(func_000425F0);
INCLUDE_ASM(func_00042790);
INCLUDE_ASM(func_00042C10);
INCLUDE_ASM(func_00043A20);
INCLUDE_ASM(func_00046400);
INCLUDE_ASM(func_00046840);
INCLUDE_ASM(func_000469C0);
INCLUDE_ASM(func_00046F30);
INCLUDE_ASM(func_00047340);

struct unk_0006 {
    /* 0x00 */ u8 * volatile ptr;
    /* 0x04 */ u8 value;
    /* 0x05 */ u8 pad_05;
}; /* size: 0x06 */

extern int D_000D4D4C;
extern struct unk_0006 *D_00182CC0;

/* void: EAX just holds a scratch pointer at ret; the callers decide. */
void func_00046800(void)
{
    int n;

    D_00182CC0--;
    while ((n = (int)D_00182CC0->ptr) != 0) {
        *D_00182CC0->ptr = D_00182CC0->value;
        D_00182CC0--;
    }
    D_000D4D4C = n;
    D_00182CC0++;
}
