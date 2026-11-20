/*
 * src/ufo2p/u_00076240.c: translation unit u_00076240 of UFO2P.EXE, 0x00076240..0x00077F30 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_00076240`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00076240);
INCLUDE_ASM(func_00076370);
INCLUDE_ASM(func_000763E0);
INCLUDE_ASM(func_00076430);
INCLUDE_ASM(func_000764C0);
INCLUDE_ASM(func_000768D0);
INCLUDE_ASM(func_00076EF0);
INCLUDE_ASM(func_000772A0);
INCLUDE_ASM(func_00077560);

extern unsigned char D_000F3DC8;
extern short D_000F3DC4;
extern unsigned char D_0016EF86;
extern short D_001A4816;

void func_000780C0(void);
void func_0002E480(void);

/* void: EAX is not set before the ret. */
void func_00077EC0(void)
{
    D_000F3DC8 = 1;
}

/* void: EAX holds only scratch (ah) at the ret. */
void func_00077ED0(void)
{
    short s;
    unsigned char c;

    s = 1;
    c = 1;
    D_000F3DC4 = s;
    D_0016EF86 = c;
    D_001A4816 = s;
    func_000780C0();
    func_0002E480();
}

/* void: EAX holds only scratch (ah) at the ret. */
void func_00077F00(void)
{
    D_000F3DC4 = 2;
    D_0016EF86 = 1;
    D_001A4816 = 1;
    func_000780C0();
    func_0002E480();
}
