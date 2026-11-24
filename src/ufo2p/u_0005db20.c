/*
 * src/ufo2p/u_0005db20.c: translation unit u_0005db20 of UFO2P.EXE, 0x0005DB20..0x0005E5E0 (D-11).
 *
 * Scaffolded by `uv run reverseapoc units UFO2P.EXE --write-src u_0005db20`, which never
 * overwrites this file. Each INCLUDE_ASM marker stands for a function that is not matched
 * yet (D-12); a matched function replaces its marker with its C.
 */
#include "common.h"

struct unk_016A {
    /* 0x000 */ u8 pad_000[4];
    /* 0x004 */ s16 unk_004;
    /* 0x006 */ u8 pad_006[0x160];
    /* 0x166 */ u8 unk_166;
    /* 0x167 */ u8 pad_167;
    /* 0x168 */ s16 unk_168;
};
struct unk_007E {
    /* 0x00 */ s16 unk_00;
    /* 0x02 */ u8 pad_02[0x7C];
};
struct unk_0094 {
    /* 0x00 */ u8 unk_00;
    /* 0x01 */ u8 pad_01[0x93];
};
extern struct unk_007E D_00128616[];
extern struct unk_0094 D_0012D950[];

void func_0005DB20(struct unk_016A *arg0)
{
    arg0->unk_168 = D_00128616[arg0->unk_004].unk_00 * D_0012D950[arg0->unk_166].unk_00 / 100;
}
extern s16 D_000D75C4[][16];
extern unsigned char D_001285E8[];

int func_0005DB80(unsigned char *self)
{
    s16 index;
    int result;
    s16 *rec;
    unsigned char *entry;
    s16 val;

    result = 1;
    rec = D_000D75C4[0];
    index = 0;
    do {
        if ((int)rec[0] == -1) {
            *(s16 *)(self + 0x108) = index;
            rec[11] = *(s16 *)(self + 0x30);
            rec[12] = *(s16 *)(self + 0x32);
            rec[13] = *(s16 *)(self + 0x34);
            *(s32 *)((unsigned char *)rec + 2) = *(s32 *)(self + 0x36);
            *(s32 *)((unsigned char *)rec + 6) = *(s32 *)(self + 0x3a);
            entry = D_001285E8 + *(s16 *)(self + 4) * 126;
            rec[6] = *(s16 *)(entry + 0x22);
            rec[7] = *(s16 *)(entry + 0x24);
            rec[8] = *(s16 *)(entry + 0x1e);
            rec[9] = *(s16 *)(entry + 0x20);
            rec[0] = *(s16 *)(entry + 0x1c);
            val = *(s16 *)(entry + 4);
            result = 0;
            rec[10] = val;
            break;
        }
        index++;
        rec += 16;
    } while (index < 200);
    return result;
}
INCLUDE_ASM(func_0005DC30);
INCLUDE_ASM(func_0005DCC0);
INCLUDE_ASM(func_0005DEF0);
INCLUDE_ASM(func_0005E140);
INCLUDE_ASM(func_0005E230);
INCLUDE_ASM(func_0005E3C0);
INCLUDE_ASM(func_0005E430);
struct unk_0276 {
    /* 0x000 */ s16 pad_000;
    /* 0x002 */ s16 unk_002;
    /* 0x004 */ u8 pad_004[0x128];
    /* 0x12C */ s16 unk_12C;
    /* 0x12E */ u8 pad_12E[0x46];
    /* 0x174 */ u8 unk_174;
    /* 0x175 */ u8 pad_175[0xFC];
    /* 0x271 */ u8 unk_271;
    /* 0x272 */ u8 pad_272[4];
};
extern struct unk_0276 D_00160FD8[];

int func_0005E500(s16 arg0)
{
    s16 index;
    int result;
    struct unk_0276 *rec;

    rec = D_00160FD8;
    result = 0;
    index = 0;
    do {
        if (rec->unk_002 != -1 && rec->unk_174 == arg0 && rec->unk_12C == 0) {
            result = 1;
            break;
        }
        index++;
        rec++;
    } while (index < 0x50);
    return result;
}

 /* size: 0x276 */


int func_0005E550(s16 arg0)
{
    s16 index;
    int result;
    struct unk_0276 *rec;

    rec = D_00160FD8;
    result = 0;
    index = 0;
    do {
        if ((int)rec->unk_002 != -1 && (s16)rec->unk_174 == arg0 && rec->unk_12C == 1
            && rec->unk_271 == 0) {
            result = 1;
            break;
        }
        index++;
        rec++;
    } while (index < 0x50);
    return result;
}

/* Records of 0x15E bytes; an id of -1 marks a free slot. Only offset 0 is read so far. */
#define REC15E_BODY_SIZE 0x15C
#define REC15E_ID_FREE -1
#define REC15E_TABLE_COUNT 50

struct rec15e {
    /* 0x000 */ s16 id;
    /* 0x002 */ u8 body[REC15E_BODY_SIZE];
}; /* size: 0x15E */

extern struct rec15e rec15e_table[];

/* rec15e_table_any_used: report whether any table slot is in use
 * Walks the 50 records of the table at 0x00179A5C and returns 1 at the first one whose
 * id is not -1 (free), else 0.
 * Address: UFO2P.EXE 0x0005E5B0
 * Evidence: table: 0x00179A5C holds 50 records of 0x15E bytes, an s16 id of -1 at +0 marks a free one
 * Evidence: call: the main loop 0x00010940 calls it with 0x0005E5E0 and 0x0005E610 before it advances the counter at 0x000D4D64
 */
int rec15e_table_any_used(void)
{
    s16 index;
    int is_used;
    struct rec15e *rec;

    rec = rec15e_table;
    is_used = 0;
    index = 0;
    do {
        if (rec->id != REC15E_ID_FREE) {
            is_used = 1;
            break;
        }
        index++;
        rec++;
    } while (index < REC15E_TABLE_COUNT);
    return is_used;
}
