/*
 * src/tacp/u_00025820.c: translation unit u_00025820 of TACP.EXE, 0x00025820..0x00028CA0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units TACP.EXE --write-src u_00025820`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_00025820);
INCLUDE_ASM(func_000258F0);
INCLUDE_ASM(func_00025970);
INCLUDE_ASM(func_000259F0);
INCLUDE_ASM(func_00025A1F);
INCLUDE_ASM(func_00025B6B);
INCLUDE_ASM(func_00025CCF);
INCLUDE_ASM(func_00025DE3);
INCLUDE_ASM(func_00025E9F);
INCLUDE_ASM(func_00025F53);
INCLUDE_ASM(func_00026007);
INCLUDE_ASM(func_0002604A);
INCLUDE_ASM(func_000260A0);
INCLUDE_ASM(func_00026197);
INCLUDE_ASM(func_0002639A);
INCLUDE_ASM(func_0002653D);
INCLUDE_ASM(func_0002673F);
INCLUDE_ASM(func_00026767);
INCLUDE_ASM(func_000267BB);
INCLUDE_ASM(func_000268E1);
INCLUDE_ASM(func_00026916);
INCLUDE_ASM(func_00026978);
INCLUDE_ASM(func_000269C2);
INCLUDE_ASM(func_00026A0A);
INCLUDE_ASM(func_00026A6C);
INCLUDE_ASM(func_00026AEB);
INCLUDE_ASM(func_00026B6C);
INCLUDE_ASM(func_00026BD3);
INCLUDE_ASM(func_00026C54);
INCLUDE_ASM(func_00026D06);
INCLUDE_ASM(func_000270EB);
INCLUDE_ASM(func_0002712A);
INCLUDE_ASM(func_000271C5);
INCLUDE_ASM(func_00027453);
INCLUDE_ASM(func_000274B5);
INCLUDE_ASM(func_000274FF);
INCLUDE_ASM(func_00027547);
INCLUDE_ASM(func_000275A9);
INCLUDE_ASM(func_000275E7);
INCLUDE_ASM(func_0002763D);
INCLUDE_ASM(func_00027678);
INCLUDE_ASM(func_000276CD);
INCLUDE_ASM(func_0002772F);
INCLUDE_ASM(func_00027793);
INCLUDE_ASM(func_000277DD);
INCLUDE_ASM(func_00027841);
INCLUDE_ASM(func_000279E2);
INCLUDE_ASM(func_00027C6D);
INCLUDE_ASM(func_00027D4B);
INCLUDE_ASM(func_00027D84);
INCLUDE_ASM(func_00027DB3);
INCLUDE_ASM(func_00027E7A);
INCLUDE_ASM(func_00027F51);
INCLUDE_ASM(func_00027FD8);
INCLUDE_ASM(func_00027FF4);
INCLUDE_ASM(func_000281A8);
INCLUDE_ASM(func_000281D7);
INCLUDE_ASM(func_00028A13);
INCLUDE_ASM(func_00028C98);

struct unk_049C {
    /* 0x000 */ s16 kind;
    /* 0x002 */ u8 pad_002[0x62];
    /* 0x064 */ s16 unk_064;
    /* 0x066 */ u8 pad_066[0x1A];
    /* 0x080 */ s16 unk_080;
    /* 0x082 */ u8 pad_082[0x41A];
}; /* size: 0x49C */

extern struct unk_049C tacrec_table[];

int func_000259B0(void)
{
    struct unk_049C *p;
    int i;
    int result;

    result = 1;
    p = tacrec_table;
    for (i = 0; i < 60; i++, p++) {
        if ((p->kind == 1 || p->kind == 12) && p->unk_064 > p->unk_080) {
            result = 0;
            break;
        }
    }
    return result;
}
