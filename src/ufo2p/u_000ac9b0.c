/*
 * src/ufo2p/u_000ac9b0.c: translation unit u_000ac9b0 of UFO2P.EXE, 0x000AC9B0..0x000ACAE0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_000ac9b0`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

INCLUDE_ASM(func_000ACA00);

struct unk_0008 {
    /* 0x00 */ s8 unk_00;
    /* 0x01 */ u8 pad_01;
    /* 0x02 */ s16 unk_02;
    /* 0x04 */ u8 pad_04[4];
}; /* size: 0x08 */

extern struct unk_0008 D_0012F9FE[];
extern u8 D_001302C6[];

int func_000AC9B0(int arg0, int arg1)
{
    struct unk_0008 *rec;
    int found;
    int index;
    int key2;
    int key;

    key = arg0;
    key2 = arg1;
    rec = D_0012F9FE;
    found = 0;
    index = 0;
    if (rec < (struct unk_0008 *)D_001302C6) {
        do {
            if (rec->unk_00 == key && rec->unk_02 == key2 && D_001302C6[index] != 0) {
                found = 1;
                break;
            }
            rec++;
            index++;
        } while (rec < (struct unk_0008 *)D_001302C6);
    }
    return found;
}
