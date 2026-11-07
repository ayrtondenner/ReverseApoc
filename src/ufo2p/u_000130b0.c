/*
 * src/ufo2p/u_000130b0.c: translation unit u_000130b0 of UFO2P.EXE, 0x000130B0..0x00013470 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000130b0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00013100);
INCLUDE_ASM(func_00013110);
INCLUDE_ASM(func_000131C0);
INCLUDE_ASM(func_00013250);

struct unk_0300 {
    /* 0x00 */ u8 data[0x300];
}; /* size: 0x300 */

extern short D_000D4CFE;

extern struct unk_0300 __syscall func_000126F0_;

void func_0001863E(void);
void func_00016F7F(struct unk_0300 *arg0);
void func_00016F03(void);
int func_00016864(void);

int func_000130B0(void)
{
    struct unk_0300 local;
    short mode;
    int result;

    local = func_000126F0_;
    mode = D_000D4CFE;
    if (mode == 6) {
        func_0001863E();
        func_00016F7F(&local);
        func_00016F03();
        result = func_00016864();
    }
    return result;
}
