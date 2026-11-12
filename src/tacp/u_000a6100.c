/*
 * src/tacp/u_000a6100.c: translation unit u_000a6100 of TACP.EXE, 0x000A6100..0x000A6D10 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_000a6100`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000A6100);
INCLUDE_ASM(func_000A61D0);
INCLUDE_ASM(func_000A6250);
INCLUDE_ASM(func_000A62C0);
INCLUDE_ASM(func_000A6300);
INCLUDE_ASM(func_000A6340);
INCLUDE_ASM(func_000A6380);
INCLUDE_ASM(func_000A63C0);
INCLUDE_ASM(func_000A6400);
INCLUDE_ASM(func_000A6440);
INCLUDE_ASM(func_000A6480);
INCLUDE_ASM(func_000A64C0);
INCLUDE_ASM(func_000A6500);
INCLUDE_ASM(func_000A6580);

struct unk_0010 {
    /* 0x00 */ u8 pad_00[4];
    /* 0x04 */ u8 kind;
    /* 0x05 */ u8 unit;
    /* 0x06 */ u8 pad_06[8];
    /* 0x0E */ s16 field_0E;
}; /* size: 0x10 */

extern char D_000E6D42[];
extern char D_001B24AC[];
extern struct unk_0010 *func_00021180(void);
int func_000AF990(int, int, int, int, int);

/* int with no return: the matched callers in this unit read EAX through int func_000A65D0(int, int). */
int func_000A65D0(int a, int b)
{
    struct unk_0010 *p;
    int i;
    int j;

    if (*(short *)D_000E6D42 != 0) {
        for (i = 0, j = 0; i < *(short *)D_000E6D42; i++) {
            p = func_00021180();
            if (p != 0) {
                p->unit = *(u8 *)((char *)D_001B24AC + j);
                p->field_0E = b;
                p->kind = a;
            }
            j += 2;
        }
    } else {
        func_000AF990(185, -11, -1, -1, 0);
    }
}

int func_000A65D0(int, int);
extern char D_00284CEE[];
extern char D_000E6CC0[];

int func_000A6640(void)
{
    int r_eax;

    r_eax = func_000A65D0(4, 0);
    *(short *)((D_00284CEE)) = 1;
    *(short *)((D_000E6CC0)) = 1;
    return r_eax;
}


int func_000A65D0(int, int);
extern char D_00284CEE[];
extern char D_000E6CC0[];

int func_000A6670(void)
{
    int r_eax;

    r_eax = func_000A65D0(4, 1);
    *(short *)((D_00284CEE)) = 1;
    *(short *)((D_000E6CC0)) = 1;
    return r_eax;
}

int func_000A65D0(int, int);
extern char D_00284CEE[];
extern char D_000E6CC0[];

void func_000A66A0(void)
{
    func_000A65D0(4, 2);
    *(short *)((D_00284CEE)) = 1;
    *(short *)((D_000E6CC0)) = 1;
}

INCLUDE_ASM(func_000A66D0);
INCLUDE_ASM(func_000A6740);
INCLUDE_ASM(func_000A67B0);
int func_000A65D0(int, int);
extern char D_00284CEE[];
extern char D_000E6CC0[];

int func_000A6820(void)
{
    int r_eax;

    r_eax = func_000A65D0(22, 0);
    *(short *)((D_00284CEE)) = 1;
    *(short *)((D_000E6CC0)) = 1;
    return r_eax;
}

INCLUDE_ASM(func_000A6850);
INCLUDE_ASM(func_000A6880);
INCLUDE_ASM(func_000A68B0);
INCLUDE_ASM(func_000A68E0);
extern char D_000E6D42[];
extern char D_000E6D44[];
extern char D_001B24AC[];
extern char D_00109EFE[];
extern char D_001EBDDC[];
int func_000AF990(int, int, int, int, int);

int func_000A69C0(void)
{
    int r_eax;

    if ((*(short *)((D_000E6D42))) == 0) goto LA6A0E;
    r_eax = *(signed char *)((D_00109EFE + ((((short *)D_001B24AC)[*(short *)((D_000E6D44))]) * 1180)));
    if ((*(signed char *)((D_00109EFE + ((((short *)D_001B24AC)[*(short *)((D_000E6D44))]) * 1180)))) != -1) goto LA6A0E;
    if ((*(int *)((D_001EBDDC))) == 0) goto LA6A00;
    *(int *)((D_001EBDDC)) = r_eax;
    return r_eax;
LA6A00:;
    *(int *)((D_001EBDDC)) = 2;
    return r_eax;
LA6A0E:;
    r_eax = func_000AF990(185, -11, -1, -1, 0);
    return r_eax;
}

INCLUDE_ASM(func_000A6A30);
INCLUDE_ASM(func_000A6B60);
INCLUDE_ASM(func_000A6C90);
